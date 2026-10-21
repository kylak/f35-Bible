#!/usr/bin/env perl
# add_italics.pl — Give the AKJV the same italics as the KJV ("ajouter les italiques").
#
# The KJV prints in italics the words its translators supplied, i.e. words that
# have no equivalent in the original languages.  In KJV.csv those words are
# bracketed:
#
#   and darkness [was] upon the face of the deep
#
# The AKJV dropped both the italics and the brackets, and lightly modernised
# the text on the way ("upon" -> "on", "hath" -> "has", "thee" -> "you", ...).
# This script puts the italic markup back, as USFM \add ... \add*:
#
#   in   \m \v 2 And the earth was without form, and void; and darkness was on the face of the deep.
#   out  \m \v 2 And the earth was without form, and void; and darkness \add was\add* on the face of the deep.
#
# The AKJV is not the KJV word for word, so a bracketed word cannot simply be
# searched for in the AKJV verse: it may have been modernised, moved, or dropped
# altogether.  Each verse is therefore aligned word by word against the KJV
# (Needleman-Wunsch, matches on the normalised word, modernised pairs such as
# hath/has counted as matches), and the "italic" flag of every KJV word is
# carried over to the AKJV word it lines up with.  "[hath]" thus marks "has".
# Consecutive italic words are merged into a single \add ... \add* span, with
# any punctuation between them left inside the span, as the KJV does.
#
# Psalm superscriptions get the italics too.  In the AKJV they are a line of
# their own ("\m ¶ A Psalm of David.") because they are not part of the verse,
# while in the KJV they open verse 1 between braces ("{¶[A Psalm] of David.}").
# Such a line is aligned with the KJV verse that follows it, so "[A Psalm]"
# still marks "A Psalm".
#
# Nothing else changes: apart from the inserted \add/\add* markers, every verse
# is byte for byte what it was, and every other line (\id, \h, \mt, \c,
# headings, \rem ...) is copied untouched.
#
# Running the script on its own output is harmless: existing \add ... \add*
# markers are removed before the alignment and put back, so the text is the
# same either way.
#
# Two quirks of KJV.csv are handled before aligning:
#   - "⌇" is a stray line-break mark of the source; it is dropped (10 rows);
#   - "⋄N" / "⋄C:V" marks where a real verse number stood in the source.  The
#     row is cut there: what precedes the mark closes the previous verse, what
#     follows it opens the marked verse ("⋄15" inside verse 15: the text before
#     it is the tail of verse 14; "⋄15" inside verse 14: the text after it is
#     the head of verse 15).  Both halves are kept and put under the verse they
#     belong to.  Only 36 CSV rows carry such a marker.
# Three verses depend on that cut: KJV.csv splits 3 John 1:14 into rows 14 and
# "15" ("⋄14Peace [be] to thee. [Our] friends salute thee..."), puts the whole
# of 2 Corinthians 13:14 in row 13:13 after a "⋄14" mark, and keeps Acts 19:41
# ("And when he had thus spoken...") as the tail of row 19:40.  Filing each
# fragment under its own verse is what lets those verses be italicised at all.
#
# Usage (same conventions as the other scripts in this project):
#   perl add_italics.pl                             # zip mode (default):
#                                                   #   clean
#                                                   #   ../4. nettoyer - page New Testament/ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd-noblank-nont.zip
#                                                   #   -> ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd-noblank-nont-ital.zip
#                                                   #   in the current directory
#                                                   #   ("ital" = italics added).
#   perl add_italics.pl <src.zip> [<out.zip>] [<kjv.csv>]
#   perl add_italics.pl <src_dir> [<out_dir>] [<kjv.csv>]   # *.usfm / *.USFM files.
#
# The KJV text defaults to KJV.csv next to this script.
# The input must be the verse-per-line output of verses_per_line.pl (one verse
# per \m line); a verse wrapped over several lines is re-joined on one line.
# Requires the Info-ZIP 'zip' and 'unzip' commands in zip mode only.

use strict;
use warnings;
use utf8;
use open ':std', ':encoding(UTF-8)';
use FindBin qw($Bin);
use File::Temp qw(tempdir);
use File::Find qw(find);

my $default_src_zip = "$Bin/../4. nettoyer - page New Testament/ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd-noblank-nont.zip";
my $default_kjv_csv = "$Bin/KJV.csv";

# Canonical position of every book, in the order KJV.csv numbers them (1..66).
my @book_codes = qw(
    GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB
    PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP
    HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI
    2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV
);
my %book_number;
@book_number{@book_codes} = (1 .. @book_codes);

# ---------------------------------------------------------------------------
# Interpret the command line
# ---------------------------------------------------------------------------
my ($src, $out, $kjv_csv);
if (@ARGV >= 1) {
    $src     = shift @ARGV;
    $out     = @ARGV >= 1 ? shift @ARGV : undef;
    $kjv_csv = @ARGV >= 1 ? shift @ARGV : $default_kjv_csv;
}
else {
    if (-f $default_src_zip) {
        $src     = $default_src_zip;
        $kjv_csv = $default_kjv_csv;
        print "Using source zip: $src\n";
    }
    else {
        die "No arguments and default source zip not found:\n  $default_src_zip\n";
    }
}
die "KJV csv not found: $kjv_csv\n" unless -f $kjv_csv;

# ---------------------------------------------------------------------------
# Load the KJV text and the position of its italics
# ---------------------------------------------------------------------------
# Returns { verse_id => { text => '...', italic => [...], brace => [...] } }.
# The brackets are removed from the text; the italic flag of every character
# says whether it was between them.  The brace flag marks the {...} blocks:
# psalm superscriptions at the head of verse 1, and the closing subscriptions
# ("{The first epistle to the Corinthians was written from Philippi...}") that
# the AKJV does not print.

# Minimal RFC 4180 reader: fields may be quoted and contain commas and "".
sub parse_csv_line {
    my ($line) = @_;
    my @fields;
    my $i = 0;
    my $len = length $line;
    while ($i <= $len) {
        my $value = '';
        if (substr($line, $i, 1) eq '"') {
            $i++;
            while ($i < $len) {
                my $c = substr($line, $i, 1);
                if ($c eq '"') {
                    if (substr($line, $i + 1, 1) eq '"') { $value .= '"'; $i += 2; }
                    else { $i++; last; }
                }
                else { $value .= $c; $i++; }
            }
            $i++ if substr($line, $i, 1) eq ',';        # field separator
        }
        else {
            my $j = index($line, ',', $i);
            $j = $len if $j < 0;
            $value = substr($line, $i, $j - $i);
            $i = $j + 1;
        }
        push @fields, $value;
        last if $i > $len;
    }
    return @fields;
}

# Repair the verse numbering slips of KJV.csv: "⌇" is noise, and "⋄N" /
# "⋄C:V" marks where the real verse number stood.  A row carrying a mark holds
# two fragments: the text before it closes the previous verse, the text after it
# opens the marked verse.  Returns ([chapter, verse, text], ...) in reading
# order, so that the caller can file each fragment under its own verse.
sub split_kjv_row {
    my ($text, $chapter, $verse) = @_;
    $text =~ s/\x{2307}//g;                       # ⌇ stray line-break mark
    my ($marker, $marked_verse, $marked_chapter) = $text =~ /(\x{22C4}(\d+)(?::(\d+))?)/;
    return ([$chapter, $verse, $text]) unless $marker;   # no mark: one verse

    my $head = substr($text, 0, $-[1]);
    my $tail = substr($text, $+[1]);

    # "⋄15" in verse 15: the text before it is the tail of verse 14.  "⋄15" in
    # verse 14: the text after it is the head of verse 15.  "⋄13:1": a chapter
    # break, whose preceding text belongs to the row's own (last) verse.
    my ($prev_chapter, $prev_verse) = defined $marked_chapter
        ? ($chapter, $verse)
        : ($chapter, $marked_verse - 1);
    my ($next_chapter, $next_verse) = defined $marked_chapter
        ? ($marked_chapter, $marked_verse)
        : ($chapter, $marked_verse);

    my @parts;
    push @parts, [$prev_chapter, $prev_verse, $head] if $prev_verse >= 1 && $head =~ /\S/;
    push @parts, [$next_chapter, $next_verse, $tail] if $tail =~ /\S/;
    return @parts;
}

# Cut the brackets (italics) and braces (titles/subscriptions) out of a KJV
# fragment, leaving one flag per character of the text that remains.
sub parse_kjv_text {
    my ($raw) = @_;
    $raw =~ s/^\s+//;
    $raw =~ s/\s+$//;
    my $plain = '';
    my (@italic, @brace);
    my ($in_italic, $in_brace) = (0, 0);
    for my $c (split //, $raw) {
        if    ($c eq '[') { $in_italic = 1; next; }
        elsif ($c eq ']') { $in_italic = 0; next; }
        elsif ($c eq '{') { $in_brace  = 1; next; }
        elsif ($c eq '}') { $in_brace  = 0; next; }
        $plain .= $c;
        push @italic, $in_italic;
        push @brace,  $in_brace;
    }
    return ($plain, \@italic, \@brace);
}

sub load_kjv {
    my ($path) = @_;
    open my $fh, '<:encoding(UTF-8)', $path or die "Cannot read $path: $!\n";

    my %verses;
    my $line_no = 0;
    while (my $line = <$fh>) {
        chomp $line;
        $line_no++;
        next if $line_no == 1 && $line =~ /^"BibleId"/;   # header
        next if $line !~ /\S/;
        my @f = parse_csv_line($line);
        die "Unexpected line $line_no in $path\n" unless @f >= 3 && $f[1] =~ /^\d+$/;

        my $book    = int($f[1] / 1_000_000);      # BCCCVVV, no zero padding
        my $chapter = int($f[1] / 1000) % 1000;
        my $verse   = $f[1] % 1000;

        # A row may hold the end of one verse and the start of another: file
        # each fragment under the verse it really belongs to, appending there
        # because the rows are read in text order.
        for my $part (split_kjv_row($f[2], $chapter, $verse)) {
            my ($chap, $vers, $raw) = @$part;
            my ($plain, $italic, $brace) = parse_kjv_text($raw);
            my $key = $book * 1_000_000 + $chap * 1000 + $vers;

            my $entry = $verses{$key};
            if (!$entry) {
                $verses{$key} = { text => $plain, italic => $italic, brace => $brace };
                next;
            }
            next unless length $plain;
            my $sep = length $entry->{text} ? ' ' : '';
            $entry->{text} .= $sep . $plain;
            push @{ $entry->{italic} }, (0) x length $sep, @$italic;
            push @{ $entry->{brace}  }, (0) x length $sep, @$brace;
        }
    }
    close $fh;
    return \%verses;
}

# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------
# A word is a run of letters/digits with internal apostrophes ("LORD's").
# Hyphens separate words ("God-ward" = "God" + "ward"), so that a hyphenated KJV
# word still lines up with the two words of the AKJV.

sub tokenize {
    my ($text) = @_;
    my @tokens;
    while ($text =~ /([\p{L}\p{N}]+(?:['\x{2019}][\p{L}\p{N}]+)*)/g) {
        push @tokens, { word => $1, start => $-[0], end => $+[0] };
    }
    return \@tokens;
}

sub normalize_word {
    my ($w) = @_;
    $w = lc $w;
    $w =~ s/\x{2019}/'/g;
    return $w;
}

# Archaic KJV forms the AKJV replaced by another word (the AKJV's own glossary,
# 95-GLO.usfm, lists most of them).  Both sides are reduced to the same key, so
# that the pair counts as a match and "hath" can mark "has".
my %modernized = (
    hath => 'has', hast => 'have',
    doth => 'does', dost => 'do', doest => 'do', didst => 'did',
    saith => 'says', sayest => 'say', saidst => 'said',
    shalt => 'shall', shouldest => 'should', wouldest => 'would',
    couldest => 'could', mayest => 'may', mightest => 'might',
    canst => 'can', wilt => 'will', knowest => 'know', knewest => 'knew',
    givest => 'give', gavest => 'gave', takest => 'take', tookest => 'took',
    makest => 'make', madest => 'made', comest => 'come', camest => 'came',
    seest => 'see', sawest => 'saw', hearest => 'hear', heardest => 'heard',
    speakest => 'speak', spakest => 'spoke', spake => 'spoke',
    goest => 'go', wentest => 'went', art => 'are', wast => 'were',
    wert => 'were', bearest => 'bear', begettest => 'beget',
    shew => 'show', shewed => 'showed', shewest => 'show', sheweth => 'shows',
    shewn => 'shown', shewing => 'showing',
    thou => 'you', thee => 'you', thy => 'your', thine => 'your',
    ye => 'you', yourselves => 'yourselves', thyself => 'yourself',
    mine => 'my', unto => 'to', upon => 'on', towards => 'toward',
    amongst => 'among', whilst => 'while', whiles => 'while', midst => 'middle',
    brethren => 'brothers', kine => 'cows', wot => 'know', wist => 'knew',
    twain => 'two', thither => 'there', hither => 'here', whither => 'where',
    whence => 'where', thence => 'from there', wherefore => 'why',
    henceforth => 'from now on', wherewith => 'with which', withal => 'with',
    ought => 'anything', nought => 'nothing', whoso => 'whoever', ere => 'before',
    begat => 'was the father of',
    lo => 'look', yea => 'yes', nay => 'no',
    shewbread => 'showbread', honour => 'honor', labour => 'labor',
    savour => 'savor', favour => 'favor', behaviour => 'behavior',
    neighbour => 'neighbor', armour => 'armor', clamour => 'clamor',
    rumour => 'rumor', valour => 'valor', vigour => 'vigor',
);

sub canonical_word {
    my ($w) = @_;                              # already normalised
    return $modernized{$w} // $w;
}

# Levenshtein distance, giving up as soon as it is known to exceed $limit.
sub edit_distance_within {
    my ($a, $b, $limit) = @_;
    my @a = split //, $a;
    my @b = split //, $b;
    return 0 if $a eq $b;
    return 99 if abs(@a - @b) > $limit;
    my @prev = (0 .. scalar @b);
    for my $i (1 .. @a) {
        my @cur = ($i);
        my $row_min = $i;
        for my $j (1 .. @b) {
            my $cost = $a[$i - 1] eq $b[$j - 1] ? 0 : 1;
            my $v = $prev[$j - 1] + $cost;                       # substitute
            my $del = $prev[$j] + 1;
            my $ins = $cur[$j - 1] + 1;
            $v = $del if $del < $v;
            $v = $ins if $ins < $v;
            $cur[$j] = $v;
            $row_min = $v if $v < $row_min;
        }
        return 99 if $row_min > $limit;
        @prev = @cur;
    }
    return $prev[scalar @b];
}

# Archaic verb endings: cometh/comes, lieth/lies, sitteth/sits, knowest/know.
# Returns true when the two words are the same verb in old and new spelling.
sub same_archaic_verb {
    my ($a, $b) = @_;
    for my $pair ([$a, $b], [$b, $a]) {
        my ($old, $new) = @$pair;
        (my $base = $old) =~ s/(?:edst|est|eth)\z// or next;
        next if length($base) < 2;
        (my $short = $base) =~ s/(.)\1\z/$1/;        # sitt-eth -> sit
        for my $stem ($base, $short) {
            return 1 if $new =~ /^\Q$stem\E(?:e?s|ed)?\z/;
        }
    }
    return 0;
}

my %similar_cache;
sub words_are_similar {
    my ($a, $b) = @_;
    # Cheap rejections, so the edit distance runs only on plausible pairs.
    return 0 if abs(length($a) - length($b)) > 2;
    return 0 if length($a) > 2 && length($b) > 2 && substr($a, 0, 1) ne substr($b, 0, 1);

    my $key = "$a\0$b";
    return $similar_cache{$key} if exists $similar_cache{$key};

    my $limit = length($a) <= 3 && length($b) <= 3 ? 0
              : length($a) >= 6 && length($b) >= 6    ? 2
              :                                        1;
    my $ok = ($limit && edit_distance_within($a, $b, $limit) <= $limit)
          || same_archaic_verb($a, $b);
    return $similar_cache{$key} = $ok ? 1 : 0;
}

# Both words are expected normalised (lowercase, plain apostrophes).  Only the
# pairs that actually match are worth remembering; the many unrelated pairs the
# alignment considers are cheap to reject and would only eat memory.
my %score_cache;
sub word_score {
    my ($a, $b) = @_;
    return 4 if $a eq $b;
    my $key = "$a\0$b";
    return $score_cache{$key} if exists $score_cache{$key};
    my $score;
    if (canonical_word($a) eq canonical_word($b)) { $score = 4; }
    elsif (words_are_similar($a, $b))             { $score = 1; }
    else                                          { return -1; }
    return $score_cache{$key} = $score;
}


# ---------------------------------------------------------------------------
# Word alignment (Needleman-Wunsch)
# ---------------------------------------------------------------------------
# Returns the list of [kjv_index, akjw_index] pairs the two texts have in
# common, in order.  A word for which one text has no counterpart is simply
# left out of the list.

sub align_words {
    my ($k, $a) = @_;
    my $n = @$k;
    my $m = @$a;
    my $gap = -2;
    my $width = $m + 1;
    my (@score, @dir);          # dir: 0 = pair, 1 = KJV word alone, 2 = AKJV word alone

    for my $i (0 .. $n) {
        for my $j (0 .. $m) {
            my $idx = $i * $width + $j;
            if ($i == 0 && $j == 0) { $score[$idx] = 0; $dir[$idx] = 0; next; }
            my $best = -1e9;
            my $d = 0;
            if ($i && $j) {
                $best = $score[($i - 1) * $width + $j - 1] + word_score($k->[$i - 1], $a->[$j - 1]);
                $d = 0;
            }
            if ($i) {
                my $s = $score[($i - 1) * $width + $j] + $gap;
                if ($s > $best) { $best = $s; $d = 1; }
            }
            if ($j) {
                my $s = $score[$i * $width + $j - 1] + $gap;
                if ($s > $best) { $best = $s; $d = 2; }
            }
            $score[$idx] = $best;
            $dir[$idx] = $d;
        }
    }

    my @pairs;
    my ($i, $j) = ($n, $m);
    while ($i > 0 || $j > 0) {
        my $d = $dir[$i * $width + $j];
        if    ($d == 0) { push @pairs, [$i - 1, $j - 1]; $i--; $j--; }
        elsif ($d == 1) { $i--; }
        else            { $j--; }
    }
    return [ reverse @pairs ];
}

# ---------------------------------------------------------------------------
# Add the italics to one verse
# ---------------------------------------------------------------------------
# $body is the verse text as it stands after "\v N ": no markers, no line
# break.  Returns $body with \add ... \add* inserted around the words the KJV
# italicises.  $is_title marks a psalm superscription (or acrostic letter) that
# sits on a line of its own in the AKJV but inside verse 1 in the KJV.

sub add_italics {
    my ($body, $id, $kjv, $stats, $is_title) = @_;

    # Starting from text that already carries italics (a second run) must give
    # the same result, not nested markers.
    $body =~ s/\\add[ \t]+(.*?)\\add\*/$1/gs;

    my $entry = $kjv->{$id};
    if (!$entry) {
        $stats->{verses_without_kjv}++ unless $is_title;
        return $body;
    }

    my $kt = tokenize($entry->{text});
    my $at = tokenize($body);

    # Italic flag of each KJV word, taken from the brackets.  In a verse body,
    # the italics of the superscriptions/subscriptions in braces do not count:
    # that text is either a title line of its own or absent from the AKJV.
    my $first_italic;
    for my $t (@$kt) {
        my $i = $t->{start};
        $t->{italic} = $entry->{italic}[$i] && ($is_title || !$entry->{brace}[$i]) ? 1 : 0;
        $first_italic ||= $t if $t->{italic};
    }
    return $body unless $first_italic;      # nothing to add in this verse
    return $body if !@$kt || !@$at;

    # Compare on normalised words; keep the original token for the positions.
    my @kw = map { normalize_word($_->{word}) } @$kt;
    my @aw = map { normalize_word($_->{word}) } @$at;
    my $pairs = align_words(\@kw, \@aw);

    # Carry the flag over.
    my $placed = my $wanted = 0;
    $wanted = grep { $_->{italic} } @$kt;
    my %pair_of;                                # AKJV word -> KJV word
    $pair_of{ $_->[1] } = $_->[0] for @$pairs;
    for my $p (@$pairs) {
        next unless $kt->[ $p->[0] ]{italic};
        $at->[ $p->[1] ]{italic} = 1;
        $placed++;
    }

    # A single KJV word may have become several AKJV words ("Forasmuch as ye
    # are" -> "For as much as you are", "wherewith" -> "with which").  Mark
    # those words too, as long as they are not the rendering of another,
    # non-italic KJV word.
    for my $p (@$pairs) {
        next unless $kt->[ $p->[0] ]{italic};
        my $word = normalize_word($kt->[ $p->[0] ]{word});
        my @forms = ([split / /, $word]);
        my $modern = canonical_word($word);
        push @forms, [split / /, $modern] if $modern =~ / /;
        for my $form (@forms) {
            my $target = join('', @$form);
            ABSORB: for my $len (2 .. 5) {
                for my $start ($p->[1] - $len + 1 .. $p->[1]) {
                    next if $start < 0 || $start + $len - 1 > $#$at;
                    my @idx = $start .. $start + $len - 1;
                    my $joined = join('', map { normalize_word($at->[$_]{word}) } @idx);
                    next unless $joined eq $target;
                    # Leave alone any word already standing for another KJV word.
                    next if grep { $_ != $p->[1] && exists $pair_of{$_} && !$kt->[ $pair_of{$_} ]{italic} }
                                 @idx;
                    $at->[$_]{italic} = 1 for @idx;
                    last ABSORB;
                }
            }
        }
    }
    $stats->{italic_words} += $wanted unless $is_title;
    $stats->{italic_words_placed} += $placed unless $is_title;

    my @marked = grep { $_->{italic} } @$at;
    if (!@marked) {
        $stats->{unplaced_verses}++ unless $is_title;
        return $body;
    }

    # Insert the markers, merging consecutive italic words into one span.
    my $result = '';
    my $pos = 0;
    my $i = 0;
    while ($i < @$at) {
        if (!$at->[$i]{italic}) { $i++; next; }
        my $j = $i;
        $j++ while $j + 1 < @$at && $at->[ $j + 1 ]{italic};
        my $start = $at->[$i]{start};
        my $end   = $at->[$j]{end};
        $result .= substr($body, $pos, $start - $pos);
        $result .= '\\add ' . substr($body, $start, $end - $start) . '\\add*';
        $pos = $end;
        $i = $j + 1;
        $stats->{spans}++;
    }
    $result .= substr($body, $pos);

    $stats->{$is_title ? 'titles_changed' : 'verses_changed'}++;
    return $result;
}

# ---------------------------------------------------------------------------
# Convert one USFM file
# ---------------------------------------------------------------------------

# One verse: "<marker> [¶ ]\v <number> <text>".
my $verse_re = qr/^(\\[A-Za-z0-9]+[ \t]+(?:\x{B6}[ \t]*)?\\v[ \t]+\d+[ \t]+)(.*)$/;

# A body paragraph line without a verse number: a psalm superscription
# ("\m ¶ A Psalm of David.") or an acrostic letter ("\m ALEPH.").  In the KJV
# these sit at the head of verse 1 (between braces), so the italics they carry
# are found by aligning them with the verse that follows.
my $title_re = qr/^(\\(?:m|p|q\d?|qc|qd|qm|qr|nb|li\d?|d)[ \t]+(?:\x{B6}[ \t]*)?)(\S.*)$/;

# Chapter and number of the first verse after line $from.
sub next_verse_number {
    my ($lines, $from, $chapter) = @_;
    for (my $i = $from + 1; $i < @$lines; $i++) {
        my $line = $lines->[$i];
        if ($line =~ /^\\c[ \t]+(\d+)/) { $chapter = $1; next; }
        if ($line =~ /$verse_re/) {
            my $prefix = $1;
            my $number = $prefix =~ /\\v[ \t]+(\d+)/ ? $1 : undef;
            return ($chapter, $number);
        }
        last if $line =~ /^\\id\b/;
    }
    return;
}

sub convert_file {
    my ($path, $kjv, $stats) = @_;
    open my $fh, '<:encoding(UTF-8)', $path or die "Cannot read $path: $!\n";
    my @lines = <$fh>;
    close $fh;

    my $book_code;
    my $chapter = 0;
    my @out;
    my $pending;                # verse not yet written out

    my $flush = sub {
        return unless $pending;
        my $book = $book_number{$book_code};
        my $new  = defined $book
            ? add_italics($pending->{body}, $book * 1_000_000 + $chapter * 1000 + $pending->{verse},
                          $kjv, $stats)
            : $pending->{body};             # book outside the 66: no KJV to match
        push @out, $pending->{prefix} . $new . $pending->{eol};
        $pending = undef;
    };

    for (my $i = 0; $i < @lines; $i++) {
        my $line = $lines[$i];
        $book_code = $1 if $line =~ /^\\id[ \t]+(\S+)/;

        my $eol = $line =~ s/(\r?\n)\z// ? $1 : '';

        # A line without a marker continues the paragraph just read.
        if ($pending && $line !~ /^\\/ && $line =~ /\S/) {
            $pending->{body} .= ' ' . $line;
            next;
        }
        $flush->();

        if ($line =~ /^\\c[ \t]+(\d+)/) {
            $chapter = $1;
            push @out, $line . $eol;
            next;
        }
        if ($line =~ /$verse_re/) {
            my ($prefix, $body) = ($1, $2);
            my $number = $prefix =~ /\\v[ \t]+(\d+)/ ? $1 : undef;
            $pending = { prefix => $prefix, body => $body, eol => $eol, verse => $number };
            next;
        }
        if ($chapter && $line =~ /$title_re/) {
            my ($prefix, $body) = ($1, $2);
            my ($chap, $number) = next_verse_number(\@lines, $i, $chapter);
            if (defined $number && $book_number{$book_code}) {
                my $id = $book_number{$book_code} * 1_000_000 + $chap * 1000 + $number;
                push @out, $prefix . add_italics($body, $id, $kjv, $stats, 1) . $eol;
                next;
            }
        }
        push @out, $line . $eol;
    }
    $flush->();

    return join('', @out);
}

# ---------------------------------------------------------------------------
# Process one or more files into $out_dir
# ---------------------------------------------------------------------------
sub convert_files {
    my ($out_dir, $kjv, @in_files) = @_;
    mkdir $out_dir unless -d $out_dir;

    my @out_files;
    my $run = {
        verses_changed       => 0,
        titles_changed       => 0,
        spans                => 0,
        italic_words         => 0,
        italic_words_placed  => 0,
        unplaced_verses      => 0,
        verses_without_kjv   => 0,
    };
    for my $f (sort @in_files) {
        (my $base = $f) =~ s!.*/!!;
        my $before = $run->{verses_changed} + $run->{titles_changed};
        my $spans  = $run->{spans};
        my $text = convert_file($f, $kjv, $run);
        open my $out, '>', "$out_dir/$base" or die "Cannot write $out_dir/$base: $!\n";
        print {$out} $text;
        close $out;
        push @out_files, "$out_dir/$base";

        my $changed = $run->{verses_changed} + $run->{titles_changed} - $before;
        my $added   = $run->{spans} - $spans;
        printf "%-42s -> %-16s (%s)\n", $base, $base,
            $changed ? sprintf("%d verse%s, %d italic span%s", $changed, $changed == 1 ? '' : 's',
                               $added, $added == 1 ? '' : 's')
                     : 'no italics';
    }
    print "\nDone. ", scalar(@in_files), " files processed in $out_dir/\n";
    printf "  %d italic span%s added in %d verse%s\n",
        $run->{spans}, $run->{spans} == 1 ? '' : 's',
        $run->{verses_changed}, $run->{verses_changed} == 1 ? '' : 's';
    printf "  %d psalm title%s also given italics\n",
        $run->{titles_changed}, $run->{titles_changed} == 1 ? '' : 's'
        if $run->{titles_changed};
    printf "  %d of %d italic word%s matched an AKJV word\n",
        $run->{italic_words_placed}, $run->{italic_words},
        $run->{italic_words} == 1 ? '' : 's';
    if ($run->{unplaced_verses}) {
        printf "  %d verse%s kept no italics because no italic word could be matched\n",
            $run->{unplaced_verses}, $run->{unplaced_verses} == 1 ? '' : 's';
    }
    if ($run->{verses_without_kjv}) {
        printf "  %d verse%s have no counterpart in the KJV csv\n",
            $run->{verses_without_kjv}, $run->{verses_without_kjv} == 1 ? '' : 's';
    }
    return @out_files;
}

# ---------------------------------------------------------------------------
# Zip a list of files into $zip_path (fresh archive, flat entries)
# ---------------------------------------------------------------------------
sub make_zip {
    my ($zip_path, @files) = @_;
    return unless @files;
    unlink $zip_path if -e $zip_path;
    my $cmd = 'zip -q -j ' . shq($zip_path) . ' ' . join(' ', map { shq($_) } @files);
    if (system($cmd) == 0) {
        printf "Compressed %d .usfm files -> %s (%d bytes)\n", scalar(@files), $zip_path, -s $zip_path;
    }
    else {
        warn "Warning: could not create $zip_path (is the 'zip' command installed?).\n";
    }
}

# Quote a string for safe use in a shell command (single quotes, escaped as needed).
sub shq {
    my ($s) = @_;
    $s =~ s/'/'"'"'/g;
    return "'$s'";
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print "Using KJV text: $kjv_csv\n";
my $kjv = load_kjv($kjv_csv);
printf "Loaded %d KJV verses\n", scalar(keys %$kjv);

if (-d $src) {
    # --- directory mode ---
    my $out_dir = defined $out ? $out : "$src-ital";
    opendir my $dh, $src or die "Cannot open $src: $!\n";
    my @in = map { "$src/$_" } sort grep { /\.usfm$/i } readdir $dh;
    closedir $dh;
    die "No *.usfm/*.USFM files found in $src\n" unless @in;

    convert_files($out_dir, $kjv, @in);
}
elsif (-f $src && $src =~ /\.zip$/i) {
    # --- zip mode ---
    my $out_zip = defined $out ? $out : do {
        (my $b = $src) =~ s!.*/!!;
        $b =~ s/\.zip$//i;
        "$b-ital.zip";
    };

    my $tmp_in  = tempdir("ital_extract.XXXXXX", CLEANUP => 1);
    my $tmp_out = tempdir("ital_out.XXXXXX",     CLEANUP => 1);

    my $rc = system('unzip', '-o', '-q', $src, '-d', $tmp_in);
    die "Failed to extract $src (is the 'unzip' command installed?)\n" if $rc != 0;

    my @usfm;
    find(sub { push @usfm, $File::Find::name if /\.usfm$/i }, $tmp_in);
    die "No *.usfm files found inside $src\n" unless @usfm;

    my @out_files = convert_files($tmp_out, $kjv, @usfm);
    make_zip($out_zip, @out_files);
}
else {
    die "Source not found or not a .zip / directory: $src\n";
}
