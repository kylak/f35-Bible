#!/usr/bin/env perl
# verses_per_line.pl — Put every verse on its own line ("versets à la ligne").
#
# Layout produced:
#   - each verse is its own \m paragraph, so printing starts every verse at
#     the left margin on a fresh line (no blank line, no indentation between
#     verses);
#   - nothing else creates a line start inside a chapter: paragraph markers
#     (\p \m \q1.. \li..), blank lines (\b) and poetry splits are flattened
#     into the verse they belong to;
#   - a new block only appears at a new chapter (\c);
#   - psalm superscriptions (\d ¶ A Psalm of David ...) and the acrostic
#     letters of Psalm 119 (\qa ALEPH. ...) are kept as their own flush line
#     at the place where they occur;
#   - ¶ paragraph marks found before a verse are kept on that verse's line
#     (they belong to the paragraph that verse starts);
#   - any remaining \cd "chapter description" line is dropped (same as
#     remove_chapter_descriptions.pl), so it is safe to run on a raw zip;
#   - everything outside chapters (\id \ide \rem \h \toc \mt ...) is left
#     untouched; files without chapters are copied unchanged.
#
# Example (Genesis 1):
#   \c 1
#   \m \v 1 In the beginning God created the heaven and the earth.
#   \m \v 2 And the earth was without form, and void; and darkness was ...
#   \m ¶ \v 6 And God said, Let there be a firmament in the middle of the ...
#
# Usage (same conventions as the other scripts in this folder):
#   perl verses_per_line.pl                            # zip mode (default):
#                                                      #   clean ../1. compiler/ENG-B-AKJV2018-pd-PSFM-master-usfm.zip
#                                                      #   -> ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl.zip
#                                                      #   in the current directory.
#   perl verses_per_line.pl <src.zip> [<out.zip>]
#   perl verses_per_line.pl <src_dir> [<out_dir>]      # *.usfm / *.USFM files.
#
# Requires the Info-ZIP 'zip' and 'unzip' commands in zip mode only.

use strict;
use warnings;
use utf8;
use open ':std', ':encoding(UTF-8)';
use FindBin qw($Bin);
use File::Temp qw(tempdir);
use File::Find qw(find);

my $default_src_zip = "$Bin/../1. compiler/ENG-B-AKJV2018-pd-PSFM-master-usfm.zip";

my $wrap_col = 2000;

# ---------------------------------------------------------------------------
# Interpret the command line
# ---------------------------------------------------------------------------
my ($src, $out);
if (@ARGV >= 1) {
    $src = shift @ARGV;
    $out = @ARGV >= 1 ? shift @ARGV : undef;
}
else {
    if (-f $default_src_zip) {
        $src = $default_src_zip;
        print "Using source zip: $src\n";
    }
    else {
        die "No arguments and default source zip not found:\n  $default_src_zip\n";
    }
}

# Body-flow markers whose marker token is dropped but whose text is kept.
my $flow_re = qr/^\\(?:m|p|q\d?|qc|qd|qm|qr|nb|li\d?|lim\d?|mi\d?|pi\d?|ph\d?|pc|pr|po|pm|pmc|pmr|pmo|lit|b|ib)\b\s?(.*)$/;

# True if $s is (spaces around) the pilcrow paragraph mark and nothing else.
sub is_pilcrow_only {
    my ($s) = @_;
    $s =~ s/\s+//g;
    return $s eq "\x{B6}";
}

# Wrap long text at spaces, ~$wrap_col chars per line (cosmetic only; a \v
# marker stays glued to its verse number, as USFM requires).
sub wrap_text {
    my ($text) = @_;
    return $text if length($text) <= $wrap_col;
    $text =~ s/\\v /\\v\x{1F}/g;
    my @words = split / /, $text;
    my $out = '';
    my $cur = '';
    for my $w (@words) {
        if (length($cur) + 1 + length($w) > $wrap_col && length $cur) {
            $out .= $cur . "\n";
            $cur = $w;
        }
        else {
            $cur .= length($cur) ? " $w" : $w;
        }
    }
    $out .= $cur if length $cur;
    $out =~ s/\x{1F}/ /g;
    return $out;
}

# Normalise a piece of verse text: collapse whitespace, trim ends.
sub norm {
    my ($s) = @_;
    $s =~ s/\s+/ /g;
    $s =~ s/^ //;  $s =~ s/ $//;
    return $s;
}

# Append one "\m ..." paragraph to @$out, separating it from the previous
# paragraph by a blank line ("\b") so each verse starts on its own line with
# an empty line before it.
sub push_para {
    my ($out, $text) = @_;
    if (@$out && $out->[-1] =~ /^\\m /) {
        push @$out, "\\b\n";
    }
    push @$out, "\\m " . $text . "\n";
}

# Turn the body lines of one chapter into "\m ..." lines (per verse).
#   $lines : array ref of body lines (no \c line inside)
sub chapter_lines {
    my ($lines) = @_;
    my @out;
    my $pilcrow = 0;          # a ¶ is pending for the next verse
    my $verse_open = 0;       # last emitted item was a verse (for continuations)

    for my $line (@$lines) {
        # --- non-body lines ------------------------------------------------
        if ($line =~ /^\\cd\b/) { next; }
        if ($line =~ /^\\(?:cl|ca)\b/) {
            push @out, $line;
            $verse_open = 0;
            next;
        }
        if ($line =~ /^\s*$/) { next; }

        # --- type of body line ---------------------------------------------
        my ($kind, $content);   # v / qa / d / flow / verbatim
        if ($line =~ /^\\v\b/) {
            $kind = 'v';
            $content = $line;
        }
        elsif ($line =~ /^\\qa\b\s?(.*)$/) {
            $kind = 'qa';
            $content = $1;
        }
        elsif ($line =~ /^\\d\b\s?(.*)$/) {
            $kind = 'd';
            $content = $1;
        }
        elsif ($line =~ $flow_re) {
            $kind = 'flow';
            $content = $1;
        }
        else {
            # Unknown marker (e.g. \h \rem at the end of a book): keep as is.
            push @out, $line if $line =~ /\S/;
            $verse_open = 0;
            next;
        }

        # --- split the content into [pre-text, verse-1, verse-2, ...] -------
        # NB: cannot use split here: perl's split ignores zero-width matches
        # at the very start of the string, so a verse beginning at position 0
        # would never be found.  Collect the offsets of every "\v N" instead.
        my @starts;
        pos($content) = 0;
        while ($content =~ /(?=\\v \d)/g) {
            push @starts, pos($content);
            pos($content) = pos($content) + 1;   # zero-width: step on manually
        }
        my @parts;
        if (@starts) {
            push @parts, substr($content, 0, $starts[0]);
            for my $k (0 .. $#starts) {
                my $end = $k < $#starts ? $starts[$k + 1] : length($content);
                push @parts, substr($content, $starts[$k], $end - $starts[$k]);
            }
        }
        else {
            push @parts, $content;    # verse-less line: everything is "pre"
        }
        my $pre = shift @parts;             # text before the first verse
        $pre = '' if !defined $pre;

        if (@parts) {
            # Lines carrying verse(s).
            if (length $pre && is_pilcrow_only($pre)) {
                $pilcrow = 1;
            }
            elsif (length $pre) {
                # Unexpected text before a verse: attach to previous verse if
                # one is open, otherwise give it its own line.
                if ($verse_open && @out) {
                    $out[-1] =~ s/\n\z//;
                    $out[-1] .= ' ' . norm($pre) . "\n";
                }
                else {
                    push_para(\@out, wrap_text(norm($pre)));
                }
            }
            for my $p (@parts) {
                my $text = norm($p);
                if ($pilcrow) {
                    $text = "\x{B6} " . $text;
                    $pilcrow = 0;
                }
                push_para(\@out, wrap_text($text));
                $verse_open = 1;
            }
            next;
        }

        # --- verse-less line ------------------------------------------------
        if ($kind eq 'v') { next; }          # cannot happen: \v implies @parts
        if (is_pilcrow_only($pre)) {
            $pilcrow = 1;                    # "\p ¶" line: ¶ starts next verse
            next;
        }
        my $text = norm($pre);
        next unless length $text;
        if ($kind eq 'qa' || $kind eq 'd' || !$verse_open) {
            # Acrostic letter, psalm superscription, or any text before the
            # first verse: its own flush line.
            push_para(\@out, wrap_text($text));
        }
        else {
            # Continuation text after the last verse (poetry line without \v).
            $out[-1] =~ s/\n\z//;
            $out[-1] .= ' ' . $text . "\n";
        }
    }
    return @out;
}

# ---------------------------------------------------------------------------
# Convert one USFM file
# ---------------------------------------------------------------------------
sub flatten_file {
    my ($path) = @_;
    open my $fh, '<', $path or die "Cannot read $path: $!";
    my @lines = <$fh>;
    close $fh;

    my @out;
    my $inchapter = 0;
    my @body;

    for my $line (@lines) {
        if ($line =~ /^\\c\b/) {
            # flush the previous chapter's body, then start a new one
            if ($inchapter) {
                push @out, chapter_lines(\@body);
                @body = ();
            }
            $inchapter = 1;
            push @out, $line;
            next;
        }
        if (!$inchapter) {
            push @out, $line unless $line =~ /^\\cd\b/;
            next;
        }
        push @body, $line;
    }
    if ($inchapter) {
        push @out, chapter_lines(\@body);
    }
    return join('', @out);
}

# ---------------------------------------------------------------------------
# Process one or more files into $out_dir
# ---------------------------------------------------------------------------
sub clean_files {
    my ($out_dir, @in_files) = @_;
    mkdir $out_dir unless -d $out_dir;

    my @out_files;
    for my $f (sort @in_files) {
        (my $base = $f) =~ s!.*/!!;
        my $text = flatten_file($f);
        open my $out, '>', "$out_dir/$base" or die "Cannot write $out_dir/$base: $!";
        print {$out} $text;
        close $out;
        push @out_files, "$out_dir/$base";
        my $changed = $text =~ /\\v \d/ && $text !~ /^\\m .*\\v \d/ ? 1 : ($text =~ /\S/ ? 1 : 0);
        printf "%-42s -> %-16s (%s)\n", $base, $base,
            $text =~ /\\v \d/ ? 'verse-per-line' : 'unchanged';
    }
    print "\nDone. ", scalar(@in_files), " files processed in $out_dir/\n";
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

sub shq {
    my ($s) = @_;
    $s =~ s/'/'\\"'\\''/g;
    return "'$s'";
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if (-d $src) {
    my $out_dir = defined $out ? $out : "$src-vpl";
    opendir my $dh, $src or die "Cannot open $src: $!";
    my @in = map { "$src/$_" } sort grep { /\.usfm$/i } readdir $dh;
    closedir $dh;
    die "No *.usfm/*.USFM files found in $src\n" unless @in;

    clean_files($out_dir, @in);
}
elsif (-f $src && $src =~ /\.zip$/i) {
    my $out_zip = defined $out ? $out : do {
        (my $b = $src) =~ s!.*/!!;
        $b =~ s/\.zip$//i;
        "$b-vpl.zip";
    };

    my $tmp_in  = tempdir("vpl_extract.XXXXXX", CLEANUP => 1);
    my $tmp_out = tempdir("vpl_out.XXXXXX",    CLEANUP => 1);

    my $rc = system('unzip', '-o', '-q', $src, '-d', $tmp_in);
    die "Failed to extract $src (is the 'unzip' command installed?)\n" if $rc != 0;

    my @usfm;
    find(sub { push @usfm, $File::Find::name if /\.usfm$/i }, $tmp_in);
    die "No *.usfm files found inside $src\n" unless @usfm;

    my @out_files = clean_files($tmp_out, @usfm);
    make_zip($out_zip, @out_files);
}
else {
    die "Source not found or not a .zip / directory: $src\n";
}
