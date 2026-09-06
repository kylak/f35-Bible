#!/usr/bin/env perl
# remove_chapter_descriptions.pl — Remove \cd "chapter description" lines from USFM files.
#
# What it removes:
#   The AKJV source text carries a \cd ("chapter description" / KJV chapter
#   argument) paragraph after almost every \c, e.g.
#
#       \c 1
#       \cd 1 The creation of Heaven and Earth, 3 of the light, 6 of the
#       firmament, ...
#       \m
#       \v 1 In the beginning God created the heaven and the earth.
#
#   PTXprint typesets that \cd paragraph as an introduction block under the
#   book title, before verse 1 of the chapter.  This script deletes those
#   lines so the printed text starts straight at verse 1.  No other marker
#   or content is touched.
#
# Usage:
#   perl remove_chapter_descriptions.pl              # zip mode (default):
#                                                    #   clean the zip produced by
#                                                    #   ../1. compiler/ENG-B-AKJV2018-pd-PSFM-master-usfm.zip
#                                                    #   (or, failing that, the same zip
#                                                    #   next to this script), and write
#                                                    #   ENG-B-AKJV2018-pd-PSFM-master-usfm-nocd.zip
#                                                    #   in the current directory.
#   perl remove_chapter_descriptions.pl <src.zip> [<out.zip>]
#                                                    # zip mode with explicit paths (out.zip
#                                                    # defaults to <src>-nocd.zip in the cwd)
#   perl remove_chapter_descriptions.pl <src_dir> [<out_dir>]
#                                                    # directory mode: clean the *.usfm /
#                                                    # *.USFM files in <src_dir> and write
#                                                    # the cleaned copies into <out_dir>
#                                                    # (defaults to <src_dir>-nocd).  Files
#                                                    # keep their names, so the result can
#                                                    # be diffed against the originals.
#
# Output keeps the input file names (e.g. 01-GEN.usfm), so a diff shows only
# the removed \cd lines.  Requires the Info-ZIP 'zip' and 'unzip' commands in
# zip mode only; directory mode needs neither.
#
# Note: \cd is a paragraph marker and always starts its own line in USFM, so
# a line-anchored removal is safe.  Lines such as \cd1... (no space) do not
# occur and are left alone.

use strict;
use warnings;
use utf8;
use open ':std', ':encoding(UTF-8)';
use FindBin qw($Bin);
use File::Temp qw(tempdir);
use File::Find qw(find);

my $default_src_zip = "$Bin/../1. compiler/ENG-B-AKJV2018-pd-PSFM-master-usfm.zip";

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
# Cleaning core: drop every line that starts a \cd paragraph
# ---------------------------------------------------------------------------
sub clean_files {
    my ($out_dir, @in_files) = @_;
    mkdir $out_dir unless -d $out_dir;

    my @out_files;
    my $total_removed = 0;
    for my $f (sort @in_files) {
        open my $in, '<', $f or die "Cannot read $f: $!";

        (my $base = $f) =~ s!.*/!!;
        open my $out, '>', "$out_dir/$base" or die "Cannot write $out_dir/$base: $!";

        my $removed = 0;
        while (my $line = <$in>) {
            # \cd is a paragraph marker: it only ever starts a line.  Drop the
            # whole line (with its line ending) when the line is "\cd", "\cd ..."
            # or "\cd   ..." (allowing \r\n endings).
            if ($line =~ /^\\cd(?:\s|$)/) {
                $removed++;
                next;
            }
            print {$out} $line;
        }
        close $in;
        close $out;
        push @out_files, "$out_dir/$base";
        $total_removed += $removed;
        printf "%-42s -> %-16s (%d cd line%s removed)\n",
            $base, $base, $removed, $removed == 1 ? '' : 's';
    }
    print "\nDone. ", scalar(@in_files), " files cleaned in $out_dir/ ($total_removed \\cd lines removed)\n";
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
    $s =~ s/'/'\\"'\\''/g;
    return "'$s'";
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if (-d $src) {
    # --- directory mode ---
    my $out_dir = defined $out ? $out : "$src-nocd";
    opendir my $dh, $src or die "Cannot open $src: $!";
    my @in = map { "$src/$_" } sort grep { /\.usfm$/i } readdir $dh;
    closedir $dh;
    die "No *.usfm/*.USFM files found in $src\n" unless @in;

    clean_files($out_dir, @in);
}
elsif (-f $src && $src =~ /\.zip$/i) {
    # --- zip mode ---
    # Output zip defaults to <zip-basename>-nocd.zip in the CURRENT directory,
    # regardless of where the source zip was found.
    my $out_zip = defined $out ? $out : do {
        (my $b = $src) =~ s!.*/!!;   # basename only
        $b =~ s/\.zip$//i;
        "$b-nocd.zip";
    };

    my $tmp_in  = tempdir("cdstrip_extract.XXXXXX", CLEANUP => 1);
    my $tmp_out = tempdir("cdstrip_out.XXXXXX",    CLEANUP => 1);

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
