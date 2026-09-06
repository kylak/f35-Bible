#!/usr/bin/env perl
# convert_psfm_to_usfm.pl — Convert AKJV PSFM (.p.sfm) files to USFM 3 and zip the result.
#
# Usage:
#   perl convert_psfm_to_usfm.pl                # zip mode (default):
#                                               #   use ENG-B-AKJV2018-pd-PSFM-master.zip
#                                               #   (in the current directory, or next to
#                                               #   this script), convert the .p.sfm files
#                                               #   it contains, and write
#                                               #   ENG-B-AKJV2018-pd-PSFM-master-usfm.zip
#                                               #   in the current directory.
#   perl convert_psfm_to_usfm.pl <src.zip> [<out.zip>]
#                                               # zip mode with explicit paths (out.zip
#                                               # defaults to <src>-usfm.zip in the cwd)
#   perl convert_psfm_to_usfm.pl <src_dir> [<out_dir>]
#                                               # directory mode (legacy): convert the
#                                               # *.p.sfm files in <src_dir>, write the
#                                               # .usfm files into <out_dir> plus a
#                                               # AKJV2018-usfm.zip there.
#
# Output files are named NN-BBB.usfm (e.g. 01-GEN.usfm, 40-INT.usfm, 95-GLO.usfm).
# Requires the Info-ZIP 'zip' and 'unzip' commands; conversion still succeeds without
# them (with a warning) except for the extraction step in zip mode.
#
# Marker mapping (PSFM -> USFM 3):
#   \b2 \b3              -> \b        (blank line, level flattened)
#   \ib2 \ib5 \ib7 \ib9  -> \b        (insert-blank, level flattened)
#   \ib                  -> \ib       (unchanged: valid USFM 3 "introduction blank line")
#   \h0 \h1 \h2          -> \rem      (placeholder headers / extra header levels)
#   \h                   -> \h        (unchanged)
#   \imt3 \imt5 \imt7    -> \imt1     (intro major titles flattened)
#   \li0                 -> \li1      (USFM list items start at level 1)
#   \nh ... \nh*         -> \sig ... \sig*   (handwritten note -> signature)
#   \q0                  -> \q1       (USFM has no level-0 poetry)
#   \toc0                -> \rem      (not linkable / not in TOC)
#   \mt7                 -> \mt2      (series/subtitle title line)
#   \mte9 ~              -> \rem ~    (page-end placeholder)
#   \cn ~                -> \rem ~    (non-standard marker; page-end placeholder)
#   \periph X            -> \rem X    (see note below)
#
# Note on \periph: PTXprint's USFM import round-trips the text through USX
# (usfmtc). Its parser treats \periph as an "internal" marker that does NOT
# close the current paragraph, so a \periph line gets nested inside the
# preceding paragraph and is re-emitted on the SAME line (e.g.
# "\imt1 New Testamant\periph Blank Page after NT title page."), which makes
# ptx2pdf fail with "Too many }'s" (the \periph macro needs to start its own
# line). Converting \periph to \rem avoids the crash: \rem is treated as a
# real paragraph boundary by the importer, stays on its own line, and the
# periph text is preserved as a (non-printed) remark. If real \periph
# sections are needed later, add them in PTXprint itself (\periph Name|id="..."
# placed directly after \id or another \periph line).
#
# All other markers (\v \p \c \cd \m \d \qa \imi \iqt \is1 \cl \bd \iq \ie \sig ...)
# are already valid USFM 3 and pass through unchanged.

use strict;
use warnings;
use utf8;
use open ':std', ':encoding(UTF-8)';
use FindBin qw($Bin);
use File::Temp qw(tempdir);
use File::Find qw(find);

my $default_src_dir = "$Bin/text-source/ENG-B-AKJV2018-pd-PSFM-master/p.sfm";
my $default_out_dir = "$Bin/text-source/ENG-B-AKJV2018-pd-PSFM-master/usfm";
my $default_zip     = 'ENG-B-AKJV2018-pd-PSFM-master.zip';

# ---------------------------------------------------------------------------
# Interpret the command line
# ---------------------------------------------------------------------------
my ($src, $out);
if (@ARGV >= 1) {
    $src = shift @ARGV;
    $out = @ARGV >= 1 ? shift @ARGV : undef;
}
else {
    # zip mode: default to the AKJV source zip, in the current directory
    # (or, failing that, in the directory where this script lives)
    if (-f $default_zip) {
        $src = $default_zip;
        print "Using source zip: $src\n";
    }
    elsif (-f "$Bin/$default_zip") {
        $src = "$Bin/$default_zip";
        print "Using source zip: $src\n";
    }
    else {
        $src = $default_src_dir;    # directory mode (legacy fallback)
        $out = $default_out_dir;
    }
}

# ---------------------------------------------------------------------------
# Conversion core: read .p.sfm files, write .usfm files into $out_dir
# ---------------------------------------------------------------------------
sub convert_files {
    my ($out_dir, @in_files) = @_;
    mkdir $out_dir unless -d $out_dir;

    my @out_files;
    for my $f (sort @in_files) {
        open my $in, '<', $f or die "Cannot read $f: $!";

        (my $base = $f) =~ s!.*/!!;
        (my $out_name = $base) =~ s/^ENG\[B\]AKJV2018\[PD\]//;
        $out_name =~ s/\.p\.sfm$/.usfm/;

        open my $out, '>', "$out_dir/$out_name" or die "Cannot write $out_dir/$out_name: $!";

        my $changed = 0;
        while (my $line = <$in>) {
            my $orig = $line;

            # --- inline character markers (anywhere in the line) ---
            # \nh* -> \sig* must run before \nh -> \sig
            $line =~ s/\\nh\*/\\sig\*/g;
            $line =~ s/\\nh/\\sig/g;

            # --- paragraph markers (line start) ---
            $line =~ s/^\\b(\d)(.*)$/\\b$2/;      # \b2 \b3
            $line =~ s/^\\ib(\d)(.*)$/\\b$2/;     # \ib2 \ib5 \ib7 \ib9
            $line =~ s/^\\h(\d)(.*)$/\\rem$2/;    # \h0 \h1 \h2
            $line =~ s/^\\imt(\d)(.*)$/\\imt1$2/; # \imt1 \imt3 \imt5 \imt7
            $line =~ s/^\\li0(.*)$/\\li1$1/;      # \li0
            $line =~ s/^\\q0(.*)$/\\q1$1/;        # \q0
            $line =~ s/^\\toc0(.*)$/\\rem$1/;     # \toc0
            $line =~ s/^\\mt7(.*)$/\\mt2$1/;      # \mt7
        $line =~ s/^\\mte9(.*)$/\\rem$1/;     # \mte9 (page-end placeholder)
        $line =~ s/^\\cn(.*)$/\\rem$1/;       # \cn (page-end placeholder)
        $line =~ s/^\\periph(.*)$/\\rem$1/;   # \periph -> \rem (avoids PTXprint import merge / ptx2pdf crash)

            print {$out} $line;
            $changed++ if $line ne $orig;
        }
        close $in;
        close $out;
        push @out_files, "$out_dir/$out_name";
        printf "%-42s -> %-14s (%d lines changed)\n", $base, $out_name, $changed;
    }
    print "\nDone. ", scalar(@in_files), " files converted to $out_dir/\n";
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
    # --- directory mode (legacy) ---
    $out //= $default_out_dir;
    opendir my $dh, $src or die "Cannot open $src: $!";
    my @in = map { "$src/$_" } sort grep { /\.p\.sfm$/ } readdir $dh;
    closedir $dh;
    die "No *.p.sfm files found in $src\n" unless @in;

    my @out_files = convert_files($out, @in);
    make_zip("$out/AKJV2018-usfm.zip", @out_files);
}
elsif (-f $src && $src =~ /\.zip$/i) {
    # --- zip mode ---
    # Output zip defaults to <zip-basename>-usfm.zip in the CURRENT directory,
    # regardless of where the source zip was found.
    my $out_zip = defined $out ? $out : do {
        (my $b = $src) =~ s!.*/!!;   # basename only
        $b =~ s/\.zip$//i;
        "$b-usfm.zip";
    };

    my $tmp_in  = tempdir("psfm_extract.XXXXXX", CLEANUP => 1);
    my $tmp_out = tempdir("usfm_out.XXXXXX",    CLEANUP => 1);

    my $rc = system('unzip', '-o', '-q', $src, '-d', $tmp_in);
    die "Failed to extract $src (is the 'unzip' command installed?)\n" if $rc != 0;

    my @sfm;
    find(sub { push @sfm, $File::Find::name if /\.p\.sfm$/ }, $tmp_in);
    die "No *.p.sfm files found inside $src\n" unless @sfm;

    my @out_files = convert_files($tmp_out, @sfm);
    make_zip($out_zip, @out_files);
}
else {
    die "Source not found or not a .zip / directory: $src\n";
}