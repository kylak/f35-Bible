#!/usr/bin/env perl
# remove_blank_lines.pl — Remove the blank \b lines that verses_per_line.pl puts
# between every verse.
#
# What it removes:
#   verses_per_line.pl lays every verse out as its own "\m" paragraph, with a
#   blank "\b" line between each one, e.g.
#
#       \m \v 1 In the beginning God created the heaven and the earth.
#       \b
#       \m \v 2 And the earth was without form, and void; ...
#       \b
#       \m ¶ \v 6 And God said, Let there be a firmament ...
#
#   This script deletes those "\b" lines so the verses sit directly one after
#   the other, without an empty line in between:
#
#       \m \v 1 In the beginning God created the heaven and the earth.
#       \m \v 2 And the earth was without form, and void; ...
#       \m ¶ \v 6 And God said, Let there be a firmament ...
#
#   Nothing else is touched: each verse keeps its own line, the leading "\m" and
#   any ¶ pilcrow are kept, and the "\c N" chapter lines stay where they are.
#
# What it keeps:
#   Only a "\b" that directly follows a verse line ("\m ...") is dropped.  The
#   blank lines used in the front matter (after "\toc3 Title", "\imt1 ...",
#   "\rem ...", "\imi ..." etc.) are NOT preceded by "\m", so they are preserved.
#   Books without chapters (e.g. the glossary 95-GLO.usfm) are left unchanged.
#
# Usage (same conventions as the other scripts in this project):
#   perl remove_blank_lines.pl                        # zip mode (default):
#                                                     #   clean
#                                                     #   ../2. nettoyer - description de chapitre/ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd.zip
#                                                     #   -> ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd-noblank.zip
#                                                     #   in the current directory.
#   perl remove_blank_lines.pl <src.zip> [<out.zip>]
#   perl remove_blank_lines.pl <src_dir> [<out_dir>]  # *.usfm / *.USFM files.
#
# Output keeps the input file names (e.g. 01-GEN.usfm), so a diff shows only the
# removed \b lines.  Requires the Info-ZIP 'zip' and 'unzip' commands in zip
# mode only; directory mode needs neither.

use strict;
use warnings;
use utf8;
use open ':std', ':encoding(UTF-8)';
use FindBin qw($Bin);
use File::Temp qw(tempdir);
use File::Find qw(find);

my $default_src_zip = "$Bin/../2. nettoyer - description de chapitre/ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd.zip";

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

# ---------------------------------------------------------------------------
# Cleaning core: drop every blank "\b" line that follows a verse line
# ---------------------------------------------------------------------------
sub clean_files {
    my ($out_dir, @in_files) = @_;
    mkdir $out_dir unless -d $out_dir;

    my @out_files;
    my $total_removed = 0;
    for my $f (sort @in_files) {
        open my $in, '<', $f or die "Cannot read $f: $!\n";

        (my $base = $f) =~ s!.*/!!;
        open my $out, '>', "$out_dir/$base" or die "Cannot write $out_dir/$base: $!\n";

        my $removed = 0;
        my $prev = '';        # the last line actually written
        while (my $line = <$in>) {
            # A "\b" line is a blank-line paragraph marker and always starts its
            # own line.  Drop it only when the line before it is a verse line
            # ("\m ..."), i.e. it is the blank line verses_per_line.pl inserted
            # between two verses.  Front-matter "\b" lines keep their preceding
            # non-\m line, so they are never matched here.
            if ($line =~ /^\\b\s*$/ && $prev =~ /^\\m\b/) {
                $removed++;
                next;
            }
            print {$out} $line;
            $prev = $line;
        }
        close $in;
        close $out;
        push @out_files, "$out_dir/$base";
        $total_removed += $removed;
        printf "%-42s -> %-16s (%d blank line%s removed)\n",
            $base, $base, $removed, $removed == 1 ? '' : 's';
    }
    print "\nDone. ", scalar(@in_files), " files cleaned in $out_dir/ ($total_removed \\b lines removed)\n";
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
    $s =~ s/'/'\"'\"'/g;
    return "'$s'";
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if (-d $src) {
    # --- directory mode ---
    my $out_dir = defined $out ? $out : "$src-noblank";
    opendir my $dh, $src or die "Cannot open $src: $!\n";
    my @in = map { "$src/$_" } sort grep { /\.usfm$/i } readdir $dh;
    closedir $dh;
    die "No *.usfm/*.USFM files found in $src\n" unless @in;

    clean_files($out_dir, @in);
}
elsif (-f $src && $src =~ /\.zip$/i) {
    # --- zip mode ---
    # Output zip defaults to <zip-basename>-noblank.zip in the CURRENT directory,
    # regardless of where the source zip was found.
    my $out_zip = defined $out ? $out : do {
        (my $b = $src) =~ s!.*/!!;   # basename only
        $b =~ s/\.zip$//i;
        "$b-noblank.zip";
    };

    my $tmp_in  = tempdir("blankstrip_extract.XXXXXX", CLEANUP => 1);
    my $tmp_out = tempdir("blankstrip_out.XXXXXX",    CLEANUP => 1);

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
