#!/usr/bin/env perl
# remove_nt_title_page.pl — Delete the generated "New Testamant" title page from the INT book.
#
# What it removes:
#   The New Testament title page is not a file of its own: it is the \imt1
#   major title carried by the introduction book, 40-INT.usfm, which sits
#   between Malachi (39) and Matthew (41):
#
#       \id INT ENG (p.sfm) -. †
#       \h ~
#       \rem New Testament
#       \b
#       \imt1 New Testamant
#       \rem Blank Page after NT title page.
#       \b
#       \h ~
#       \rem ~
#
#   PTXprint typesets that \imt1 as a full title page in front of the New
#   Testament.  This script deletes it, so the printed volume no longer gets
#   that page: the cover prepared in PTXprint is what appears instead.
#   Nothing is added anywhere.
#
#   In 40-INT.usfm only, the script therefore drops:
#     - every \imt1 ... line (the NT title itself — it is the only \imt in the
#       file), and
#     - a \rem ... line directly following a dropped \imt1 line, i.e. in the
#       AKJV source "\rem Blank Page after NT title page.", which only
#       documents the page being removed.
#   Deleting the title leaves its two neighbouring "\b" blank lines back to
#   back, so consecutive "\b" lines are collapsed into a single one.
#
#   In the AKJV source the NT title is the only thing 40-INT.usfm holds, so
#   once it is gone the book has no printable paragraph left at all.  PTXprint
#   then refuses it with a canonical-check error ("INT : Empty file"), so in
#   that case the script drops 40-INT.usfm entirely instead of writing a hollow
#   file.  Nothing else is dropped, and every other book is copied byte for
#   byte, so a diff of the output against the input shows only 40-INT.usfm
#   disappearing.
#
# Usage (same conventions as the other scripts in this project):
#   perl remove_nt_title_page.pl                        # zip mode (default):
#                                                       #   clean
#                                                       #   ../3. nettoyer - lignes vides/ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd-noblank.zip
#                                                       #   -> ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd-noblank-nont.zip
#                                                       #   in the current directory
#                                                       #   ("nont" = no NT title page).
#   perl remove_nt_title_page.pl <src.zip> [<out.zip>]
#   perl remove_nt_title_page.pl <src_dir> [<out_dir>]  # *.usfm / *.USFM files.
#
# Output keeps the input file names, so a diff shows only 40-INT.usfm (and,
# when the book still has printable text, the removed title page lines and the
# collapsed \b line inside it).
# Requires the Info-ZIP 'zip' and 'unzip' commands in zip mode only; directory
# mode needs neither.

use strict;
use warnings;
use utf8;
use open ':std', ':encoding(UTF-8)';
use FindBin qw($Bin);
use File::Temp qw(tempdir);
use File::Find qw(find);

my $default_src_zip = "$Bin/../3. nettoyer - lignes vides/ENG-B-AKJV2018-pd-PSFM-master-usfm-vpl-nocd-noblank.zip";

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
# Cleaning core: drop the NT title page from the INT book
# ---------------------------------------------------------------------------

# A line carries printed content unless it is one of the "invisible" markers
# (identification, running header, comment, blank line, TOC index entry) or has
# no text after the marker.  PTXprint's canonical check works the same way: a
# book whose every paragraph is invisible or empty is reported as an empty file.
my %non_printing = map { $_ => 1 } qw(id h rem b ide usfm sts toc);
sub book_has_content {
    my ($line) = @_;
    return 0 unless $line =~ /^\s*\\([A-Za-z0-9]+)\s*(.*)$/s;
    my ($mkr, $rest) = (lc $1, $2);
    $mkr =~ s/\d+$//;                 # \imt1 -> \imt, \toc3 -> \toc
    return 0 if $non_printing{$mkr};
    return $rest =~ /\S/ ? 1 : 0;     # the marker must also have some text
}

sub clean_files {
    my ($out_dir, @in_files) = @_;
    mkdir $out_dir unless -d $out_dir;

    my @out_files;
    my $total_removed          = 0;
    my $total_blanks_collapsed = 0;
    my $total_books_dropped    = 0;
    for my $f (sort @in_files) {
        open my $in, '<', $f or die "Cannot read $f: $!\n";

        (my $base = $f) =~ s!.*/!!;

        # The NT title page only exists in the introduction book.
        my $is_int = $base =~ /-INT\.usfm\z/i;

        my $removed          = 0;
        my $blanks_collapsed = 0;
        my $drop_next_rem    = 0;   # a \imt1 was just dropped: drop its \rem too
        my $prev_blank       = 0;   # the line kept last was a "\b"
        my @kept;
        while (my $line = <$in>) {
            if ($is_int) {
                # The title line itself ("\imt1 New Testamant") ...
                if ($line =~ /^\\imt\d*\b/) {
                    $removed++;
                    $drop_next_rem = 1;
                    next;
                }
                # ... and the \rem that only documents the removed page.
                if ($drop_next_rem && $line =~ /^\\rem\b/) {
                    $removed++;
                    $drop_next_rem = 0;
                    next;
                }
                $drop_next_rem = 0;
                # Without the title, its two "\b" lines sit next to each other.
                if ($line =~ /^\\b\s*$/ && $prev_blank) {
                    $blanks_collapsed++;
                    next;
                }
            }
            push @kept, $line;
            $prev_blank = $line =~ /^\\b\s*$/ ? 1 : 0;
        }
        close $in;

        # Removing the title can leave the INT book with nothing printable at
        # all.  PTXprint would then reject it as an empty file (canonical
        # check), so drop the whole book instead of writing the hollow rest.
        if ($is_int && !grep { book_has_content($_) } @kept) {
            $total_books_dropped++;
            printf "%-42s -> %-16s (%s)\n", $base, '(dropped)', 'no printable content left';
            next;
        }

        open my $out, '>', "$out_dir/$base" or die "Cannot write $out_dir/$base: $!\n";
        print {$out} @kept;
        close $out;
        push @out_files, "$out_dir/$base";
        $total_removed          += $removed;
        $total_blanks_collapsed += $blanks_collapsed;

        my $note = 'unchanged';
        if ($is_int) {
            $note = sprintf "%d title page line%s removed", $removed, $removed == 1 ? '' : 's';
            $note .= sprintf ", %d blank line%s collapsed", $blanks_collapsed, $blanks_collapsed == 1 ? '' : 's'
                if $blanks_collapsed;
        }
        printf "%-42s -> %-16s (%s)\n", $base, $base, $note;
    }
    print "\nDone. ", scalar(@in_files), " files processed in $out_dir/ ($total_removed title page line";
    print $total_removed == 1 ? '' : 's';
    print " removed";
    print ", $total_blanks_collapsed blank line" . ($total_blanks_collapsed == 1 ? '' : 's') . " collapsed"
        if $total_blanks_collapsed;
    print ", $total_books_dropped book" . ($total_books_dropped == 1 ? '' : 's') . " dropped"
        if $total_books_dropped;
    print ")\n";
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
if (-d $src) {
    # --- directory mode ---
    my $out_dir = defined $out ? $out : "$src-nont";
    opendir my $dh, $src or die "Cannot open $src: $!\n";
    my @in = map { "$src/$_" } sort grep { /\.usfm$/i } readdir $dh;
    closedir $dh;
    die "No *.usfm/*.USFM files found in $src\n" unless @in;

    clean_files($out_dir, @in);
}
elsif (-f $src && $src =~ /\.zip$/i) {
    # --- zip mode ---
    # Output zip defaults to <zip-basename>-nont.zip in the CURRENT directory,
    # regardless of where the source zip was found.
    my $out_zip = defined $out ? $out : do {
        (my $b = $src) =~ s!.*/!!;   # basename only
        $b =~ s/\.zip$//i;
        "$b-nont.zip";
    };

    my $tmp_in  = tempdir("nttitle_extract.XXXXXX", CLEANUP => 1);
    my $tmp_out = tempdir("nttitle_out.XXXXXX",    CLEANUP => 1);

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
