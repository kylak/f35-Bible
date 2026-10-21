#!/usr/bin/env perl
# checking.t — Tests for add_italics.pl.
#
# Each run builds a miniature corpus (a handful of USFM books and a miniature
# KJV.csv) in a temporary directory, calls the script exactly as the pipeline
# does — directory mode, then zip mode — and checks the USFM it writes.
#
# The verses below are copied from the real AKJV files and KJV.csv, so the
# expectations are the ones the full run produces:
#
#   GEN 1:2    a plain \add ... \add* span                    ([was])
#   GEN 1:3    a verse KJV.csv does not have                  (left alone)
#   PSA 23:4   an archaic word the AKJV modernised            ([art] -> "are")
#   PSA 30:1   a psalm superscription on a line of its own    ([and], [at])
#   3JN 1:14   a verse KJV.csv splits over two rows           (⋄14)
#   1CO 7:33   a verse KJV.csv splits over two rows           (⋄34)
#   1CO 7:34   the second half of that split                  ([also], [her])
#
# Usage (from "5. ajouter les italiques/"; "prove" alone would only look in t/):
#   prove tests/checking.t
#   perl tests/checking.t         # same, with a readable summary

use strict;
use warnings;
use utf8;

use Test::More;
use File::Temp qw(tempdir);
use File::Basename qw(dirname);
use File::Spec;
use Cwd qw(abs_path);

my $script = abs_path(File::Spec->catfile(dirname(__FILE__), '..', 'add_italics.pl'));
ok(-f $script, 'add_italics.pl is next to tests/') or BAIL_OUT("cannot find $script");

# ---------------------------------------------------------------------------
# The mini corpus
# ---------------------------------------------------------------------------

my %book = (
    '01-GEN.usfm' => <<'END',
\id GEN ENG (p.sfm)
\ide UTF-8
\h Genesis
\mt Genesis
\c 1
\m \v 1 In the beginning God created the heaven and the earth.
\m \v 2 And the earth was without form, and void; and darkness was on the face of the deep. And the Spirit of God moved on the face of the waters.
\m \v 3 And God said, Let there be light: and there was light.
END
    '19-PSA.usfm' => <<'END',
\id PSA ENG (p.sfm)
\ide UTF-8
\h Psalms
\mt Psalms
\c 23
\m \v 4 Yes, though I walk through the valley of the shadow of death, I will fear no evil: for you are with me; your rod and your staff they comfort me.
\c 30
\m ¶ A Psalm, and song at the dedication of the house of David.
\m \v 1 I will extol you, O LORD; for you have lifted me up, and have not made my foes to rejoice over me.
END
    '47-1CO.usfm' => <<'END',
\id 1CO ENG (p.sfm)
\ide UTF-8
\h 1 Corinthians
\mt 1 Corinthians
\c 7
\m \v 33 But he that is married cares for the things that are of the world, how he may please his wife.
\m \v 34 There is difference also between a wife and a virgin. The unmarried woman cares for the things of the Lord, that she may be holy both in body and in spirit: but she that is married cares for the things of the world, how he may please her husband.
END
    '65-3JN.usfm' => <<'END',
\id 3JN ENG (p.sfm)
\ide UTF-8
\h 3 John
\mt 3 John
\c 1
\m \v 13 I had many things to write, but I will not with ink and pen write to you:
\m \v 14 But I trust I shall shortly see you, and we shall speak face to face. Peace be to you. Our friends salute you. Greet the friends by name.
END
);

# Rows copied verbatim from KJV.csv.  GEN 1:3 is deliberately absent.
my @kjv = (
    q{KJV,1001001,¶In the beginning God created the heaven and the earth.},
    q{KJV,1001002,"And the earth was without form, and void; and darkness [was] upon the face of the deep. And the Spirit of God moved upon the face of the waters."},
    q{KJV,19023004,"Yea, though I walk through the valley of the shadow of death, I will fear no evil: for thou [art] with me; thy rod and thy staff they comfort me."},
    q{KJV,19030001,"{¶A Psalm [and] Song [at] the dedication of the house of David.} ¶I will extol thee, O LORD; for thou hast lifted me up, and hast not made my foes to rejoice over me."},
    q{KJV,46007033,"But he that is married careth for the things that are of the world, how he may please [his] wife. ⋄34There is difference [also] between a wife and a virgin."},
    q{KJV,46007034,"The unmarried woman careth for the things of the Lord, that she may be holy both in body and in spirit: but she that is married careth for the things of the world, how she may please [her] husband."},
    q{KJV,64001013,"I had many things to write, but I will not with ink and pen write unto thee:"},
    q{KJV,64001014,"But I trust I shall shortly see thee, and we shall speak face to face."},
    q{KJV,64001015,⋄14Peace [be] to thee. [Our] friends salute thee. Greet the friends by name.},
);

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

sub spew {
    my ($path, $text) = @_;
    open my $fh, '>:encoding(UTF-8)', $path or die "Cannot write $path: $!\n";
    print {$fh} $text;
    close $fh;
}

sub slurp {
    my ($path) = @_;
    open my $fh, '<:encoding(UTF-8)', $path or die "Cannot read $path: $!\n";
    local $/;
    my $text = <$fh>;
    close $fh;
    return $text // '';
}

# Run the script; returns (its output, exit status).
sub run_italics {
    my @args = @_;
    open my $pipe, '-|', $^X, $script, @args or die "Cannot run $script: $!\n";
    local $/;
    my $log = <$pipe>;
    close $pipe;
    my $status = $? >> 8;
    return ($log // '', $status);
}

# The line of book $name holding verse $number.
sub verse_line {
    my ($path, $name, $number) = @_;
    my ($line) = grep { /^\\[mp] (?:\x{B6} )?\\v \Q$number\E / } split /\n/, slurp($path);
    return defined $line ? $line : "<no \\v $number in $name>";
}

sub build_corpus {
    my $root = tempdir('add_italics_test.XXXXXX', CLEANUP => 1, TMPDIR => 1);
    mkdir "$root/in" or die "Cannot create $root/in: $!\n";
    spew("$root/in/$_", $book{$_}) for sort keys %book;
    spew("$root/KJV.csv", qq{"BibleId","VerseId","Content"\n} . join("\n", @kjv) . "\n");
    return $root;
}

# ---------------------------------------------------------------------------
# Directory mode
# ---------------------------------------------------------------------------

my $root = build_corpus();
my $out  = "$root/out";
my ($log, $status) = run_italics("$root/in", $out, "$root/KJV.csv");

is($status, 0, 'directory mode exits 0');
like($log, qr/^Done\. 4 files processed/m, 'processes the four books');
like($log, qr/\d+ italic spans added in \d+ verse/, 'reports the italics it added');
like($log, qr/\b1 verse\b.*no counterpart in the KJV csv/, 'reports the verse KJV.csv does not have');

my @written = sort glob("$out/*.usfm");
is(scalar @written, 4, 'writes one output file per book');

is(verse_line("$out/01-GEN.usfm", 'GEN', 1),
   '\m \v 1 In the beginning God created the heaven and the earth.',
   'a verse whose KJV has no italics is untouched');

like(verse_line("$out/01-GEN.usfm", 'GEN', 2),
     qr/and darkness \\add was\\add\* on the face of the deep\./,
     'marks the supplied word ([was])');

is(verse_line("$out/01-GEN.usfm", 'GEN', 3),
   '\m \v 3 And God said, Let there be light: and there was light.',
   'leaves alone a verse with no row in KJV.csv');

like(verse_line("$out/19-PSA.usfm", 'PSA', 4),
     qr/for you \\add are\\add\* with me; your rod and your staff/,
     'follows the AKJV wording ([art] marks "are")');

my ($title) = grep { /^\\m (?!\\v )/ && /\bPsalm\b/ } split /\n/, slurp("$out/19-PSA.usfm");
is($title, '\m ¶ A Psalm, \add and\add* song \add at\add* the dedication of the house of David.',
   'marks a psalm superscription, which is a line of its own in the AKJV');

like(verse_line("$out/65-3JN.usfm", '3JN', 13),
     qr/write to you:$/,
     'leaves the verse before a split alone');

like(verse_line("$out/65-3JN.usfm", '3JN', 14),
     qr/Peace \\add be\\add\* to you\. \\add Our\\add\* friends salute you\. Greet the friends by name\.$/,
     'joins the two KJV.csv rows of a split verse (3 John 1:14)');

like(verse_line("$out/47-1CO.usfm", '1CO', 33),
     qr/how he may please \\add his\\add\* wife\.$/,
     'marks the half of a split verse that stays with its own verse');

like(verse_line("$out/47-1CO.usfm", '1CO', 34),
     qr/There is difference \\add also\\add\* between a wife and a virgin\./,
     'marks the half of a split verse that belongs to the next one');

# The markup must be well formed: every opening \add has its closing \add*,
# no span is empty, and no span contains another.
my ($open, $close, $empty, $nested) = (0, 0, 0, 0);
for my $file (@written) {
    my $text = slurp($file);
    $open   += () = $text =~ /\\add /g;
    $close  += () = $text =~ /\\add\*/g;
    $empty  += () = $text =~ /\\add \\add\*/g;
    $nested += () = $text =~ /\\add [^\\]*\\add [^\\]*\\add\*/g;
}
is($open, $close, 'every \add has a closing \add*');
cmp_ok($open, '>', 0, 'some italics were added');
is($empty, 0, 'no empty \add span');
is($nested, 0, 'no nested \add span');

# Apart from the markers, every file is the input byte for byte.
for my $file (@written) {
    (my $base = $file) =~ s!.*/!!;
    my $plain = slurp($file);
    $plain =~ s/\\add (.*?)\\add\*/$1/gs;
    is($plain, slurp("$root/in/$base"), "removing the markers gives back $base");
}

# ---------------------------------------------------------------------------
# Second run: the output of a run is its own input
# ---------------------------------------------------------------------------

my ($log2, $status2) = run_italics($out, "$root/out2", "$root/KJV.csv");
is($status2, 0, 'second run exits 0');
for my $file (@written) {
    (my $base = $file) =~ s!.*/!!;
    is(slurp("$root/out2/$base"), slurp($file), "second run reproduces $base");
}

# ---------------------------------------------------------------------------
# Zip mode (the default invocation of the pipeline)
# ---------------------------------------------------------------------------

sub tool_available {
    my ($tool) = @_;
    my $null = File::Spec->devnull;
    return system("$tool -v >$null 2>&1") == 0;
}

SKIP: {
    skip 'zip and unzip are needed for zip mode', 4
        unless tool_available('zip') && tool_available('unzip');

    my $zip = "$root/corpus.zip";
    my @in  = sort glob("$root/in/*.usfm");
    is(system('zip', '-q', '-j', $zip, @in), 0, 'builds a source zip');

    my $out_zip = "$root/corpus-ital.zip";
    my ($zlog, $zstatus) = run_italics($zip, $out_zip, "$root/KJV.csv");
    is($zstatus, 0, 'zip mode exits 0');
    like($zlog, qr/Compressed 4 \.usfm files -> \Q$out_zip\E/, 'writes the output zip');

    my $unpacked = "$root/unzipped";
    mkdir $unpacked;
    is(system('unzip', '-o', '-q', $out_zip, '-d', $unpacked), 0, 'unpacks the output zip');

    like(verse_line("$unpacked/01-GEN.usfm", 'GEN', 2),
         qr/\\add was\\add\*/,
         'the zip holds the same italics as directory mode');
}

done_testing();
