#!/usr/bin/perl -w
############################################################
#
#  gallery.cgi - Simple Image Gallery Script
#
#  Author:    Nicola Worthington <nicolaworthington@msn.com>
#  Version:   1.25
#  Date:      2002-11-14
#  Copyright: (c)2002 Nicola Worthington. All rights reserved.
#
############################################################

# nicolaw V1.25 2002-11-14
### - Added first_thumbnail and last_thumbnail keywords.
### - Added debug output logging to a seperate file.

# nicolaw V1.24 2002-11-07
### - Added unlinking of pod2htmd.x~~ and pod2htmi.x~~ files after
###   execution of pod2html for documentation display.
### - Fixed bug in send_tmpl() where $template was trying to look for
###   %CONF->{gallery}->{uri}->... instead of the correct
###   %CONF->{gallery}->{$GALLERYURL}->...
### - Added the 'description' directive to the gallery config scope
###   and template macro variables

# nicolaw V1.23 2002-11-04
### Made the checking of permissions before moving and resizing of
### files a little more robust so that it doesn't fuck up half way
### through doing stuff - just dies or warns in error logs instead.
### Also added @ and ' to allowed characters in untaint()

# nicolaw V1.22 2002-10-31
### Fixed a bug whereby ThumbDir directories were not being created
### if perl was running with taint checking enabled, because the
### string passed to mkdir was tainted.
### Added highres/lowres seperation using the following config file
### directives:
###   HighResVersion
###   HighResMinDim
###   LowResMaxDim
###   LowResQuality
###   HighResDir
###   HighResPrefix

# nicolaw V1.21 2002-10-20
### Adding online documentation in POD format. Calling the CGI with
### the QUERY_STRING of perldoc|man|help|manual will display the
### documentation.

# nicolaw V1.20 2002-10-18
### Added the following config file directives:
###   CanvasColour
###   CanvasWidth
###   CanvasHeight
###   Overlay
###   OverlayGravity
### The canvas options allow you to specify an exact size for each
### thumbnail. The ThumbMaxDim is applied to the resized thumbail image
### which is then cropped and overlayed on top of the canvas. If the
### thumbnail image is smaller than the canvas dimensions, then you
### will be able to see the coloured canvas behind the thumbnail.
### The overlay option allows you to overlay a transparent gif logo
### for example, over the whole canvas, with a gravity of:
###    North. NorthEast, East, SouthEast, South, SouthWest, West,
###    NorthWest or Center
### I use the Overlay option to put a framed bracket over the canvas
### mounted thumbnail. 

# nicolaw V1.19 2002-09-06
### Added file sizes in bytes, kb, mb and gb for videos and images for
### templates, and added video information too

# nicolaw V1.18 2002-09-05
### Trying to optimize proprocessing methods for generating thumbnails
### for large video files

# nicolaw V1.17 2002-09-04
### Added support for MPEG and AVI movies to be thumbnailed in to
### a story board film strip (experimental at the moment, and
### requires mpeg2decode to be installed in the path)

# nicolaw V1.16 2002-08-25
### Added TMPL_VAR{single_page} variable name for template to indicate
### if there is only a single page of images to display

# nicolaw V1.15 2002-08-23
### Improved the gallery directory translation logic a little bit. Its
### still not perfect, but it will work in 90% of installation
### scenarios I think.
### There is still a known problem whereby you cannot place a gallery
### directly in the document root of a site, because gallery.cgi thinks
### that you have not specified a gallery location. This will be
### fixed in the next release with any luck

# nicolaw V1.14 2002-08-07
### Added &nuke=1 option for deleting entire galleries from the server
### for those pesky situations when your web server has shitty httpd
### runtime permissions and you cannot delete the thumbnails via ftp

# nicolaw V1.13 2002-08-05
### Added error handling for perl modules which are not installed
### Fixed case sensitive directory handling for gallery directives

sub debug {
	if ($DEBUG) {
		my $msg = "@_"; chomp $msg;
		my @months = qw/Jan Feb Mar Apr Man Jun Jul Aug Sep Oct Nov Dec/;
		my ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
		print D sprintf("%s %s %d [%02d/%3s/%04d:%02d:%02d:%02d] %s\n",
					$ENV{REMOTE_HOST} || $ENV{REMOTE_ADDR} || '-',
					$ENV{REMOTE_USER} || '-',
					$PID,
					$mday,$months[$mon],$year+1900,$hour,$min,$sec,
					$msg);
	}
}

BEGIN {
	use 5.6.0;
	use strict;
	use English;
	#use constant DEBUG => 1;
	use subs qw(debug);
	use vars qw($VERSION $MOI $Q %FORM %TMPL_VAR %CONF %DESC %DEFAULTS $CFGFILE
		$GALLERYURL $GALLERYDIR $DOCUMENT_ROOT $TILDAUSER $USERDIR $USERHOME $DEBUG);

	$DEBUG = 1;
	$ENV{PATH} = '/bin:/usr/bin:/usr/local/bin';
	$VERSION = 1.25;
	$WARNING = 1;
	if ($PROGRAM_NAME =~ m|^([/_\-\.a-zA-Z0-9]+)$|) { $PROGRAM_NAME = $1; }
	($MOI = $PROGRAM_NAME) =~ s|.*/||;
	$OUTPUT_AUTOFLUSH = 1;

	if ($DEBUG) {
		open(D,">>${MOI}_debug.log") || warn "Unable to open file handle D for file '${MOI}_debug.log': $!\n";
		debug '------------------------------------------------------------';
	}

	### Print online documentation if asked
	if ($ENV{QUERY_STRING} =~ /^perldoc|pod|instructions|readme|install|help|man|manual$/i) {
		print "Content-type: text/html\n\n";
		open(PH,"pod2html $PROGRAM_NAME|")
			|| die "Failed to open pipe handle for command 'pod2html $PROGRAM_NAME': $!\n";
		print while (<PH>);
		close(PH) || die "Failed to close pipe handle for command 'pod2html $PROGRAM_NAME': $!\n";
		unlink 'pod2htmd.x~~';
		unlink 'pod2htmi.x~~';
		exit;
	}

	### Try to load Perl modules
	Try2Load({
			'File::Copy'		=> '',
			'Image::Magick'		=> '',
			'Image::Info'		=> 'qw(image_info dim)',
			'HTML::Entities'	=> '',
			'HTML::Template'	=> '',
			'CGI'			=> 'qw(:standard)',
			'CGI::Carp'		=> 'qw(fatalsToBrowser)',
			'CGI::SSI'		=> '',
			'MPEG::Info'		=> '',
			'Data::Dumper'		=> '',
		});

	sub Try2Load {
		my %modules = %{$_[0]};
		my $sad = 0;
		while (my ($module,$args) = each %modules) {
			eval("use $module $args;");
			if ($@) { # Failed to load module
				$sad++;
				$modules{$module} = 0;
			} else { $modules{$module} = 1; } # It was okay
		}
		if ($sad) {
			print "Content-type: text/html\n\n<h1>$MOI</h1>";
			print <<_HTML_;
				<html><head><title>$MOI</title></head><body>
				<h1>Software Error</h1><p>$MOI failed to load one or more Perl module.</p>
				<table border="2" width="300" bgcolor="#ffffff">
					<tr>
						<th>Module</th>
						<th>Status</th>
					</tr>
_HTML_
			while (my ($module,$loaded_okay) = each %modules) {
				print "<tr><td align='left'>$module</td><td>";
				unless ($loaded_okay) {
					print "<font color='#bb0000'>Not installed</font>";
				} else {
					#my $foo = "${module}::VERSION";
					#PRINT "<FONT COLOR='#00BB00'>V".${$FOO}." INSTALLED</FONT>";
					print "<font color='#00bb00'>Installed</font>";
				}
				print "</td></tr>\n";
			}
			(my $podurl = $ENV{REQUEST_URL}) =~ s/(&|\?)?.*/\?pod/;
			print "</table>\n<p><a href=\"$podurl\">Click here for $ENV{SCRIPT_NAME} documentation</a>.</body>\n</html>\n";
			exit;
		}
	}
}

### Basic assumptions
$USERDIR = 'public_html';
$CFGFILE = 'gallery.conf';

$Q = new CGI;
%FORM = $Q->Vars;

################
### First try and translate the physical gallery directory on the disk
#if ($ENV{REQUEST_URI} =~ /$ENV{SCRIPT_NAME}(\?.*)?/) { # Called directly as a CGI
# ~user/ (~/public_html) sites require special directory translation and therefore
# cannot currently be viewed by referencing the gallery.cgi directly and supplying
# a gallery=foo value pair
if ($ENV{REQUEST_URI} =~ /$ENV{SCRIPT_NAME}((\?|&).*)?/) { # Called directly as a CGI
	$TMPL_VAR{'method_cgi'} = 1;
	die "No gallery specified: please define 'gallery' parameter" unless $FORM{gallery};
	$GALLERYURL = $FORM{gallery};
	$GALLERYDIR = "$ENV{DOCUMENT_ROOT}$FORM{gallery}";

} else { # Possibly called as an SSI
	$TMPL_VAR{'method_ssi'} = 1;
#	(my $uri = $ENV{REQUEST_URI}) =~ s/\?.*$//;
	(my $uri = $ENV{REQUEST_URI}) =~ s/(\?|&).*$//;
	($GALLERYDIR = "$ENV{DOCUMENT_ROOT}$uri"); # The gallery directory location
	&junk_document_name; # Just the document_name if it's snuck in there

	sub junk_document_name {
		# Junk off the document_name if it was included in the url
		if (-f $GALLERYDIR && $GALLERYDIR =~ /\/$ENV{DOCUMENT_NAME}$/) {
			(my $guess = $GALLERYDIR) =~ s/\/$ENV{DOCUMENT_NAME}$//;
			$GALLERYDIR = $guess if -d $guess;
		}
	}

	# Called as an SSI from within a users ~/public_html webspace
	if ($uri =~ /^\/~([\d\w\_]+)?\/?(.*)/ && !-d $GALLERYDIR) {
		$TILDAUSER = $1; # The username of the home directory
		$USERHOME = (getpwnam($TILDAUSER))[7]; # The users home directory
		$GALLERYDIR = "$USERHOME/$USERDIR/$2"; # The gallery directory location
	}
	&junk_document_name; # Junk the document_name if it's snuck in there
}
$GALLERYDIR =~ s|/+$||; # Chop off trailing /'s

### Now make the URL of the gallery based on the gallery directory location and stuff
if ($USERHOME) { # ~user accounts via SSI
	($GALLERYURL = $GALLERYDIR) =~ s|^$USERHOME/$USERDIR|/~$TILDAUSER|; # The gallery URL
	$CFGFILE = "$USERHOME/$USERDIR/$CFGFILE"; # The gallery.conf file location

} elsif (!$GALLERYURL) { # All other SSI accounts
	($GALLERYURL = $GALLERYDIR) =~ s/^$ENV{DOCUMENT_ROOT}//; # The gallery URL
}

$GALLERYDIR =~ s|//|/|g; ### nicolaw 2002-08-08 remove dupe //'s to single / (cheating I know - sorry)

#debug "-----------------------\n";
#debug "GALLERYDIR = $GALLERYDIR\n";
#debug "GALLERYURL = $GALLERYURL\n";
#debug "CFGFILE = $CFGFILE\n";
#debug "USERHOME = $USERHOME\n";
#debug "TILDAUSER = $TILDAUSER\n";
#debug "-----------------------\n";

### Set defaults assumed if not configured in the gallery.conf file
%DEFAULTS = (
	imagemask		=> '\.(jpe?g|Tiff?|tiff?|Png|png|Gif|gif|JPE?G|TIFF?|PNG|GIF|mpe?g|MPE?G|AVI|avi|Jpe?g|Mpe?g)',
	thumbquality	=> 50,
	thumbdir		=> 'thumbnails',
	thumbprefix		=> '_',
	thumbmaxdim		=> 90,
	thumbtemplate	=> "$MOI.tmpl",
	imagetemplate	=> "$MOI.view.tmpl",
	columns			=> 3,
	rows			=> 5,
	descriptions	=> 'descript.ion',
	pagequicklinks	=> 10,
	filmcolor		=> 'black',
	framemaxdim		=> '70',
	framespacing	=> 2,
	maxframes		=> 5,
	highresversion	=> 'off',
	highresmindim	=> 641,
	lowresquality	=> 80,
	lowresmaxdim	=> 580,
	highresdir		=> 'hires',
	highresprefix	=> '+',
);

# Merge in our config with the defaults
read_config($CFGFILE);
while (my ($k,$v) = each %DEFAULTS) {
	$CONF{$k} = $v unless exists $CONF{$k};
}

#die "cfgfile = $CFGFILE<br>\n
#galleryurl = $GALLERYURL<br>\n
#gallerydir = $GALLERYDIR<br>\n";

### Cry and have a tantrum if the gallery directory location doesn't exist
$DOCUMENT_ROOT = $CONF{document_root} || $ENV{DOCUMENT_ROOT};
die "Gallery path '$GALLERYDIR' does not exist" unless -d $GALLERYDIR;
die "Cannot read from gallery path '$GALLERYDIR'" unless (-r $GALLERYDIR && -x $GALLERYDIR);

### nicolaw 2002-08-08 added ability to nuke galleries if your ftp login doesn't have
###                 permission to nuke httpd process generated files or directories
if ($FORM{nuke}) { # Nuke a gallery directory completely
	#debug 'Nuke';
	die "No gallery password defined in $CFGFILE; unable to nuke gallery"
		if !%CONF->{gallery}->{$GALLERYURL}->{password};
	my $password = %CONF->{gallery}->{$GALLERYURL}->{password} || %CONF->{password};
	if ($FORM{nuke} ne $password) { die "Authentication failure"; }
	else {
		print header;
		#my $regex = qr($CONF{imagemask});
		my $regex = qr(%CONF->{gallery}->{$GALLERYURL}->{imagemask} || $CONF{imagemask});
		nuke_tree($GALLERYDIR,$regex);
		sub nuke_tree {
			my ($path,$regex) = @_;
			opendir(DH,$path) || die "Unable to open directory handle DH for directory '$path': $!\n";
			my @ary = grep { !/^\.\.?$/ } readdir(DH);
			closedir(DH) || die "Unable to close directory handle DH for directory '$path': $!\n";
			for (@ary) {
				if (-d "$path/$_" && $_ eq $CONF{thumbdir}) { nuke_tree("$path/$_",$regex); }
				else {
					next unless $_ =~ /$regex/i; 
					print "Deleting &quot;$_&quot; ...<br>\n";
					unlink "$path/$_";
				}
			}
			(my $quick_path = $path) =~ s|^.*/||;
			print "Removing &quot;$quick_path&quot; ...<br>\n";
			rmdir $path;
		}
		exit(0);
	}
}

read_descriptions("$GALLERYDIR/$CONF{descriptions}");

build_tmpl { # Build our pretty little template hash
	my $c = $FORM{c} || %CONF->{gallery}->{$GALLERYURL}->{columns} || $CONF{columns} || 3; # Columns per page
	my $r = $FORM{r} || %CONF->{gallery}->{$GALLERYURL}->{rows} || $CONF{rows} || 5; # Rows per page
	my $p = $FORM{p} || 1; # Current page
	my $img = exists $FORM{image} ? $FORM{image} : '';

	my $highres = 0; # HighResVersion
	if (exists $FORM{highres}) {
		$img = $FORM{highres};
		$highres = 1;
	}

	build_template("$GALLERYDIR/$img",$c,$r,$p,$highres);
}

send_tmpl { # Send our wonderful template to our luser with love and kisses
	my $template = $FORM{template} ||
			($FORM{image} || $FORM{highres} ?
				%CONF->{gallery}->{$GALLERYURL}->{imagetemplate} || $CONF{imagetemplate} :
				%CONF->{gallery}->{$GALLERYURL}->{thumbtemplate} || $CONF{thumbtemplate}) ||
			%CONF->{gallery}->{$GALLERYURL}->{template} || $CONF{template};
	die "No template specified: please define 'thumbtemplate' and 'imagetemplate' or 'template' in your configuration file"
		unless $template;
	send_template($template);
}

exit(0);





############################################################

sub read_config {
	debug sprintf("read_config('%s')",join("','",@_));
	my $file = shift;
	if (-e $file && open(FH,$file)) {
		%CONF = slurp();
		sub slurp {
			my $closetype = shift;
			my %foo;
			while (<FH>) {
				### nicolaw 2002-08-08 Escaped the # to make syntax highlighting work in vim
				next if (m!^\s*(\#|//|;|\s*$)!); # Skip comments and empty lines
				if (/^\s*<\s*([^\/\s]+)(?:\s+\"?(.+?)\"?)?\s*>\s*$/) {
					# my ($type,$key) = (lc($1),lc($2));
					### nicolaw 2002-08-05 - make key values case sensitive to allow case sensitive directories in the Gallery directives
					my ($type,$key) = (lc($1),$2);
					if ($key) { %foo->{$type}->{$key} = slurp($type); }
					else      { %foo->{$type}         = slurp($type); }
				} elsif (/^\s*(\S+)\s+\"?(.+?)\"?\s*$/) {
					%foo->{lc($1)} = $2;
				} elsif (/^\s*<\s*\/\s*$closetype\s*>\s*$/i) {
					return \%foo;
				}
			}
			die "read_config() Error: '$closetype' scope directive is not closed\n" if $closetype;
			return %foo;
		}
		close(FH) || warn "Unable to close file handle FH for file '$file': $!\n";
	} else {
		warn "Unable to open file handle FH for file '$file': $!\n";
	}
}

sub read_descriptions {
	debug sprintf("read_descriptions('%s')",join("','",@_));
	my $file = shift;
	if (-e $file && open(FH,$file)) {
		while (<FH>) {
			if (/^\s*\"?(.+?)\"?:?\s+(.+?)\s*$/) {
				$DESC{$1} = $2;
			}
		}
		close(FH) || warn "Unable to close file handle FH for file '$file': $!\n";
	}
}

sub build_template {
	debug sprintf("build_template('%s')",join("','",@_));
	my ($target,$c,$r,$p,$highres) = @_; # Use (c)olumns, (r)ows, (p)age number, (hires)

	@TMPL_VAR{qw(rows columns)} = ($r,$c);
	($TMPL_VAR{self} = $ENV{REQUEST_URI}) =~ s/\?.*//;
	$TMPL_VAR{GALLERY} = $GALLERYURL;
	$TMPL_VAR{title} = %CONF->{gallery}->{$GALLERYURL}->{title};
	$TMPL_VAR{gallery_description} = %CONF->{gallery}->{$GALLERYURL}->{description};

	my @images;
	directoryTarget: {
		### If the *original* target was an image, then flange it in this scope to still build the
		### listing template too :)
		my $tgt_dir = $target;
		$tgt_dir =~ s|/[^/]+$|| unless -d $tgt_dir;

		@images = list_files($tgt_dir, (%CONF->{gallery}->{$GALLERYURL}->{imagemask} || $CONF{imagemask}));
		$TMPL_VAR{total_images} = @images;

		$TMPL_VAR{total_pages} = @images / ( $r * $c );
		$TMPL_VAR{total_pages}++ if $TMPL_VAR{total_pages} > int $TMPL_VAR{total_pages};
		$TMPL_VAR{total_pages} = int $TMPL_VAR{total_pages};
		$TMPL_VAR{single_page} = 1 if $TMPL_VAR{total_pages} == 1;
		die "Page $p is invalid; there are only $TMPL_VAR{total_pages} pages in this gallery.\n" if $p > $TMPL_VAR{total_pages};

		my $quicklinks = %CONF->{gallery}->{$GALLERYURL}->{pagequicklinks} || $CONF{pagequicklinks};
		my $qloffset = int($quicklinks * 0.4);
		my ($start,$end) = (1,1);
		my $foo = 0;

		# One page only, first page or last page
		if ($quicklinks >= $TMPL_VAR{total_pages} || $p - $qloffset < 1 || $p + ($quicklinks - $qloffset) > $TMPL_VAR{total_pages}) {
			if ($quicklinks >= $TMPL_VAR{total_pages}) { # Less pages than quick links
				$start = 1;
				$end = $TMPL_VAR{total_pages};
				$foo = 'a';
			} else {
				if ($p + ($quicklinks - $qloffset) > $TMPL_VAR{total_pages}) {
					$start = $TMPL_VAR{total_pages} - ($quicklinks - 1);
					$end = $TMPL_VAR{total_pages};
					$foo = 'b';
				} else {
					$start = 1;
					$end = $quicklinks;
					$foo = 'c';
				}
			}
		} else {
			$start = $p - $qloffset;
			$end = $p + ($quicklinks - $qloffset) - 1;
			$foo = 'd';
		}
		#$TMPL_VAR{GOO} = "<pre>start = $start\np = $p\nend = $end\nquicklinks = $quicklinks\nqloffset = $qloffset\nfoo = $foo</pre>";
		my $x = 0;
		for (my $i = $start; $i <= $end; $i++) {
			%TMPL_VAR->{PAGEQUICKLINKS}->[$x]->{page} = $i;
			%TMPL_VAR->{PAGEQUICKLINKS}->[$x]->{current} = 1 if $i == $p;
			$x++;
		}
		$TMPL_VAR{page} = $p;

		# We're looking at displaying a gallery (directory) and not a specific view of an individual image
		if (-d $target) {
			my $ThumbDir = untaint("$tgt_dir/$CONF{thumbdir}/");
			#mkdir $ThumbDir,0777 unless -d $ThumbDir;
			mkdir $ThumbDir unless -d $ThumbDir;
			#chmod $ThumbDir,0777;
			die "build_template(): Failed to create thumbnail directory '$ThumbDir'\n" unless -d $ThumbDir;

			my $HighResDir = untaint("$tgt_dir/$CONF{highresdir}/");
			unless ($HighResVersion =~ /^\s*(off|no|none)\s*$/i) {
				#mkdir $HighResDir,0777 unless -d $HighResDir;
				mkdir $HighResDir unless -d $HighResDir;
				#chmod $HighResDir,0777;

				die "build_template(): Failed to create highres directory '$HighResDir'\n" unless -d $HighResDir;
				die "build_template(): Unable to write to highres directory '$HighResDir'\n" unless -w $HighResDir && -x $HighResDir;
				#die "build_template(): Unable to write to target directory '$target'\n" unless -w $target && -x $target;
			}

			my $HighResMinDim = %CONF->{gallery}->{$GALLERYURL}->{highresmindim} || $CONF{highresmindim};
			my $HighResVersion = %CONF->{gallery}->{$GALLERYURL}->{highresversion} || $CONF{highresversion};

			my ($row,$col) = (0,0);
			my $x = 0;
			for ($x = (($c*$r)*$p)-($c*$r); $x < $c*$r*$p; $x++) {
				my $tgt_img = $images[$x];
				last unless $tgt_img;

				my $imagefile   = "${target}$tgt_img";
				my $thumbfile   = "${target}$CONF{thumbdir}/$CONF{thumbprefix}$tgt_img";
				my $highresfile = untaint("${target}$CONF{highresdir}/$CONF{highresprefix}$tgt_img");

				$thumbfile .= '.jpg' if $imagefile =~ /\.(mpe?g|avi)$/i; # Videos have image thumbnails, not video thumbnails
				# if ($imagefile =~ /\.(mpe?g|avi)$/i) { $thumbfile =~ s|\.[^\.]+$|\.jpg|; } ### Videos have image thumbnails, not video thumbnails :)

				$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{filename}	= encode_entities($tgt_img);
				$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{image_uri}	= "$GALLERYURL/".encode_url($tgt_img);
				$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{thumbnail_uri}	= "$GALLERYURL/$CONF{thumbdir}/".encode_url("$CONF{thumbprefix}$tgt_img");

				# Videos have image thumbnails, not video thumbnails :)	
				if ($TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{thumbnail_uri} =~ /\.(mpe?g|avi)$/i) { 
					#$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{thumbnail_uri} =~ s|\.[^\.]+$|\.jpg|;
					$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{thumbnail_uri} .= '.jpg';
					$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{video} = 1;
				}
				$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{description} = encode_entities($DESC{$tgt_img});

				# Generate a thumbnail image if one doesn't already exist
				debug "Generating thumbnail image for '$imagefile' ...\n" unless -e $thumbfile;
				generate_thumbnail(
					$imagefile,
					$thumbfile,
					%CONF->{gallery}->{$GALLERYURL}->{thumbmaxdim} || $CONF{thumbmaxdim},
					%CONF->{gallery}->{$GALLERYURL}->{thumbquality} || $CONF{thumbquality}
				) unless -e $thumbfile;

				# Populate the template hash with information about the main image
				my ($ImageWidth,$ImageHeight) = populate_image_info($imagefile,'image_',$row,$col);

				# Populate the template hash with information about the thumbnail image
				my ($ThumbWidth,$ThumbHeight) = populate_image_info($thumbfile,'thumbnail_',$row,$col);

				# Is HighResVersion enabled
				unless ($HighResVersion =~ /^\s*(off|no|none)\s*$/i) {

					# and if this a highres image which needs to be moved in to
					# the HighResDir and have a lowres version made to replace the original?
					if (!-f $highresfile && ($ImageWidth >= $HighResMinDim || $ImageHeight >= $HighResMinDim)) { # yes ...

						# only start this process if we have write permissions on the original
						# image file,.. otherwise we might copy the original in to the highres dir,
						# then try to resize the original, only to find that we cannot write to
						# it, thereby leaving a highres version in the highres directory and in the
						# main directory. that would be stupid!
						if (-r $imagefile && -w $imagefile) {
							my $imagefile = untaint($imagefile);
							File::Copy::copy($imagefile, $highresfile);

							if (-f $highresfile) { # If the copy was sucessfull then replace the original with a lowres copy
								debug "Generating lowres image for '$imagefile' ...\n";
								generate_thumbnail(
									$imagefile,
									$imagefile,
									%CONF->{gallery}->{$GALLERYURL}->{lowresmaxdim} || $CONF{lowresmaxdim},
									%CONF->{gallery}->{$GALLERYURL}->{lowresquality} || $CONF{lowresquality},
									'NoCanvasOrOverlaysPlease'
								); # Don't be fooled that we're using generate_thumbnail() - remember we're passing in the filenames and dimensions! :)

							} else { # otherwise if it failed for some reason, we're a little buggered! :-(
								warn "Warning: failed to copy original imagefile '$imagefile' to highresfile '$highresfile'\n";
							}

						} else { # we didn't have read and write permissions on the original image
							warn "Warning: we don't have read and write permissions on original imagefile '$imagefile' in order to create a low-res version\n";
						}
					}

					# If the highresfile is in place (from before or just created - doesn't matter which), then make the links available
					if (-f $highresfile) {
						$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{highres} = 1;
					}
				}

				$col++;
				if ($col >= $c) {
					$row++;
					$col = 0;
				}
			}
			$TMPL_VAR{prev_page} = $p-1 if $p > 1;
			$TMPL_VAR{next_page} = $p+1 if @images > $x;
			$TMPL_VAR{first_thumbnail} = (($c*$r)*$p)-($c*$r) + 1;
			$TMPL_VAR{last_thumbnail} = $x;
		}
	}

	### View a single image
	if (-f $target) {
		(my $tgt_img = $target) =~ s|^.*/||;
		(my $tgt_dir = $target) =~ s|/[^/]+$||;
		my $thumbfile = "$tgt_dir/$CONF{thumbdir}/$CONF{thumbprefix}$tgt_img";
		$thumbfile .= '.jpg' if $thumbfile =~ /\.(mpe?g|avi)$/i; # Videos have image thumbnails, not video thumbnails :)
		# if ($thumbfile =~ /\.(mpe?g|avi)$/i) { $thumbfile =~ s|\.[^\.]+$|\.jpg|; } ### Videos have image thumbnails, not video thumbnails :)

		$TMPL_VAR{filename}	= encode_entities($tgt_img);
		$TMPL_VAR{description} = encode_entities($DESC{$tgt_img});

		for (my $x = 0; $x < @images; $x++) {
			$TMPL_VAR{current_image} = $x + 1 if $images[$x] eq $tgt_img;
		}

		if ($highres) { ## This is a **really** nasty hack and much be fixed!
			$TMPL_VAR{image_uri}	= "$GALLERYURL/$CONF{highresdir}/".encode_url("$CONF{highresprefix}$tgt_img");
			my ($ImageWidth,$ImageHeight) = populate_image_info("$tgt_dir/$CONF{highresdir}/$CONF{highresprefix}$tgt_img",'image_');
		} else { ## This is a really nasty hack and much be fixed!
			$TMPL_VAR{image_uri}	= "$GALLERYURL/".encode_url($tgt_img);
			my ($ImageWidth,$ImageHeight) = populate_image_info($target,'image_');
		}

		{
			my @schema = qw(dev ino mode nlink uid gid rdev size atime mtime ctime blksize blocks);
			my %stat;
			@stat{@schema} = stat($thumbfile);
			while (my ($k,$v) = each %stat) {
				$TMPL_VAR{"image_${k}_localtime"} = localtime($v) if $k =~ /^.time$/;
				$TMPL_VAR{"image_$k"} = encode_entities($v);
			}
		}

		my ($ThumbWidth,$ThumbHeight) = populate_image_info($thumbfile,'thumbnail_');
	}

	# Debug information - hey, why not? :)
	$TMPL_VAR{TMPL_VAR} = Dumper(\%TMPL_VAR);
	$TMPL_VAR{CONF} = Dumper(\%CONF);
	$TMPL_VAR{DEFAULTS} = Dumper(\%DEFAULTS);
}

sub send_template {
	debug sprintf("send_template('%s')",join("','",@_));
	my $templfile = shift;
	my $template = HTML::Template->new(
		filename => $templfile,
		die_on_bad_params => 0,
		loop_context_vars => 1,
		global_vars => 1,
		associate => $Q,
		path => [
			"$DOCUMENT_ROOT/cgi-bin", "$DOCUMENT_ROOT",
			'cgi-bin', '../cgi-bin', '..'
		]
	);
	$template->param(%TMPL_VAR);

	my $html = $template->output;
	$ENV{REQUEST_URI} = %CONF->{gallery}->{$GALLERYURL}->{title} || $GALLERYURL; ### Nicola's specific modification
	my $ssi = CGI::SSI->new();
	# while (my ($k,$v) = each %ENV) { $ssi->set($k => $v); }
	$html = $ssi->process($html);

	print header,$html;
}

sub generate_thumbnail {
	debug sprintf("generate_thumbnail('%s')",join("','",@_));
	my ($imagefile,$thumbfile,$maxdim,$quality,$nofrills) = @_;
	(my $tgt_img = $imagefile) =~ s|^.*/||;
	$nofrills ||= 0;

	### Handle regular images (anything *but* .MPEG and .AVI files) as normal thumbnails
	unless ($imagefile =~ /\.(mpe?g|avi)$/i) {

		my $canvascolour = %CONF->{gallery}->{$GALLERYURL}->{canvascolour} || $CONF{canvascolour} || '#e6d8cd';
		my $canvaswidth = %CONF->{gallery}->{$GALLERYURL}->{canvaswidth} || $CONF{canvaswidth};
		my $canvasheight = %CONF->{gallery}->{$GALLERYURL}->{canvasheight} || $CONF{canvasheight};
		my $canvas = '';
		if (!$nofrills && $canvaswidth && $canvasheight && $canvascolour !~ /^\s*(off|no|none)\s*$/i
			&& $canvaswidth !~ /^\s*(off|no|none)\s*$/i && $canvasheight !~ /^\s*(off|no|none)\s*$/i) {
		 	$canvas = new Image::Magick;
			$canvas->Set(size=>"${canvaswidth}x${canvasheight}");
			$canvas->ReadImage("xc:$canvascolour") if $canvascolour;
		}

		my $overlayfile = %CONF->{gallery}->{$GALLERYURL}->{overlay} || $CONF{overlay};
		my $overlaygravity = %CONF->{gallery}->{$GALLERYURL}->{overlaygravity} || $CONF{overlaygravity} || 'Center';
		my $overlay = '';
		if (!$nofrills && $overlayfile && -r $overlayfile && $overlayfile !~ /^\s*(off|no|none)\s*$/i
			&& $overlaygravity !~ /^\s*(off|no|none)\s*$/i) {
			$overlay = new Image::Magick;
			$overlay->Read($overlayfile);
		}

		my $image = new Image::Magick;
		$image->Read($imagefile);
		if (ref $image) {
			my ($ox,$oy) = $image->Get('width','height');
			$ox ||= 1; $oy ||= 1;
			my $r = $ox>$oy ? $ox / $maxdim : $oy / $maxdim;
			#$image->Resize(
			$image->Sample(
				width => $ox/$r,
				height => $oy/$r,
				blur => 1,
			#	filter => 'Cubic'
			);

			if (ref $canvas) {
				$canvas->Composite(image=>$image, compose=>'over', gravity=>'Center');
				$image = $canvas;
				undef $canvas;
			}

			if (ref $overlay) {
				$image->Composite(image=>$overlay, compose=>'over', gravity=>$overlaygravity);
			}

			$image->Comment(string => $DESC{$tgt_img}||$tgt_img);
			$image->Set(quality => $quality);
			$image->Write($thumbfile);
			#chmod $thumbfile,0666;
		}

	} else { ### Handle .MPEG and .AVI files differently (make a storyboard thumbnail)
		my $thumbmaxdim = %CONF->{gallery}->{$GALLERYURL}->{thumbmaxdim} || $CONF{thumbmaxdim};
		my $framemaxdim = %CONF->{gallery}->{$GALLERYURL}->{framemaxdim} || $CONF{framemaxdim};
		my $maxframes = %CONF->{gallery}->{$GALLERYURL}->{maxframes} || $CONF{maxframes};
		my $framespacing = %CONF->{gallery}->{$GALLERYURL}->{framespacing} || $CONF{framespacing};

		# Fix really stupid mistakes on the part of the lusers
		$thumbmaxdim = $framemaxdim + ($CNOF{framespacing} * 2) if
			$thumbmaxdim < $framemaxdim + ($framespacing * 2);

		my $video_info = MPEG::Info->new( -file => $imagefile );
		$video_info->probe();

		#debug "---\n";
		#debug "imagefile    = '$imagefile'\n";
		#debug "thumbfile    = '$thumbfile'\n";
		#debug "-\n";
		#debug "maxframes    = '$maxframes'\n";
		#debug "framespacing = '$framespacing'\n";
		#debug "-\n";
		#for (qw/type acodec acodecraw achans arate astreams width height vstreams vcodec vframes vrate/) {
		#	debug sprintf("%-12s = '%s'\n", $_, $video_info->$_);
		#}

	#	my ($moviewidth, $movieheight) = ($video_info->width, $video_info->height);
	#	$moviewidth ||= 1; $movieheight ||= 1;
	#	my $movieframes = $video_info->vframes;

		my $r;
		my $movie = Image::Magick->new;
		$r = $movie->Read($imagefile);
		warn "$r" if "$r";

		my ($moviewidth, $movieheight) = $movie->Get('width','height');
		$moviewidth ||= 1; $movieheight ||= 1;

		my $ratio       = $moviewidth > $movieheight ? $moviewidth / $framemaxdim : $movieheight / $framemaxdim;
		my ($framewidth, $frameheight) = (int $moviewidth / $ratio, int $movieheight / $ratio);
		my $movieframes = @{$movie};
		my $thumbheight = $frameheight + ($framespacing * 8);

		my $thumbwidth;
		my $thumbframes = $maxframes + 1;
		do {
			$thumbframes--;
			$thumbwidth = ($framewidth * $thumbframes) + ($framespacing * $thumbframes+1);
		} until ($thumbwidth <= $thumbmaxdim);
		my $steping     = int $movieframes / $thumbframes;

		my $thumb = Image::Magick->new;
		$r = $thumb->Set(size=>"${thumbwidth}x${thumbheight}");
		warn $r if $r;

		$r = $thumb->ReadImage("xc:$CONF{filmcolour}");
		warn $r if $r;

		### Don't use the immediately first frame if possible - offset the start a little
		my $ioffset = $steping > 0 ? int $steping / 2 : 0; 

		my @load_frames;
		for (my $i = 0+$ioffset; $i < $movieframes; $i += $steping) {
			push @load_frames, $i;
		}
		my $imagefile_inc_frames = sprintf("%s[%s]", $imagefile, join(',',@load_frames));

		#debug "-\n";
		#debug "framewidth   = '$framewidth'\n";
		#debug "frameheight  = '$frameheight'\n";
		#debug "-\n";
		#debug "movieframes  = '$movieframes'\n";
		#debug "moviewidth   = '$moviewidth'\n";
		#debug "movieheight  = '$movieheight'\n";
		#debug "-\n";
		#debug "ratio        = '$ratio'\n";
		#debug "steping      = '$steping'\n";
		#debug "ioffset      = '$ioffset'\n";
		#debug "load_frames  = '@load_frames'\n";
		#debug "-\n";
		#debug "quality      = '$quality'\n";
		#debug "thumbmaxdim  = '$thumbmaxdim'\n";
		#debug "thumbframes  = '$thumbframes'\n";
		#debug "thumbwidth   = '$thumbwidth'\n";
		#debug "thumbheight  = '$thumbheight'\n";
		#debug "framemaxdim  = '$framemaxdim'\n";
		#debug "-\n";

		#my $movie = Image::Magick->new;
		#$r = $movie->Read($imagefile_inc_frames);
		#warn $r if $r;

		for (my $i = 0; $i < $thumbframes; $i++) {
			#debug "Resizing movie frame $i ($load_frames[$i]) to ${framewidth}x${frameheight} and adding as thumb frame $i ...\n";
			$r = $movie->[$load_frames[$i]]->Resize(width=>$framewidth, height=>$frameheight);
			warn "$r" if "$r";

			$r = $thumb->Composite(
					image	=> $movie->[$load_frames[$i]],
					compose	=> 'Over',
					x	=> $framespacing + 
						   ($i * $framemaxdim) + 
						   ($i * $framespacing),
					y	=> $framespacing * 4
				);
			warn $r if $r;
		}

		#debug "---\n";

		my $rand = 0 - $framespacing + int(rand($framespacing*2));
		for my $top (($framespacing, $thumbheight - ($framespacing*3))) {
			for (my $i = $rand; $i < $thumbwidth; $i += $framespacing * 4) {
				$r = $thumb->Draw(
						stroke    => 'white',
						primitive => 'rectangle',
						fill      => 'white',
						points    => sprintf("%d,%d %d,%d",
							$i, $top, $i+($framespacing*2), $top+($framespacing*2)-1 )
					);
				warn $r if $r;
			}
		}

		$thumb->Comment(string => $DESC{$tgt_img}||$tgt_img);
		$thumb->Set(quality => $quality);
		$thumbfile =~ s|\.[^\.]+$|\.jpg|;
		$r = $thumb->Write($thumbfile);
		warn $r if $r;
	}
}

sub populate_image_info {
	debug sprintf("populate_image_info('%s')",join("','",@_));
	my ($file,$type,$row,$col) = @_;
	my $info = image_info($file);

	my $video_info;
	if ($file =~ /\.(AVI|MPE?G)$/i) { ### Get video information also
		$video_info = MPEG::Info->new( -file => $file );
		$video_info->probe();
	}

	if (defined $row && defined $col) { ### Display a page of video/image thumbnails
		$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{"${type}size_gb"} = commify( sprintf("%11.2f", (-s $file)/1024/1024/1024) );
		$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{"${type}size_mb"} = commify( sprintf("%11.2f", (-s $file)/1024/1024) );
		$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{"${type}size_kb"} = commify( sprintf("%11.2f", (-s $file)/1024) );
		$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{"${type}size_b"} = commify(-s $file);

		foreach (keys %{$info}) {
			$TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{"${type}$_"} = encode_entities($info->{$_})
				unless ref $info->{$_};
		}
		if ($video_info) {
			for (qw/type acodec acodecraw achans arate astreams width height vstreams vcodec vframes vrate/) {
		        $TMPL_VAR{ROW}->[$row]->{COL}->[$col]->{"${type}$_"} = $video_info->$_;
			}
		}

	} else { ### Display simple image/video
		$TMPL_VAR{"${type}size_gb"} = commify( sprintf("%11.2f", (-s $file)/1024/1024/1024) );
		$TMPL_VAR{"${type}size_mb"} = commify( sprintf("%11.2f", (-s $file)/10241024) );
		$TMPL_VAR{"${type}size_kb"} = commify( sprintf("%11.2f", (-s $file)/1024) );
		$TMPL_VAR{"${type}size_b"} = commify(-s $file);

		foreach (keys %{$info}) {
			$TMPL_VAR{"${type}$_"} = encode_entities($info->{$_}) unless ref $info->{$_};
		}
		if ($video_info) {
			for (qw/type acodec acodecraw achans arate astreams width height vstreams vcodec vframes vrate/) {
		        $TMPL_VAR{"${type}$_"} = $video_info->$_;
			}
		}
	}

	return ($info->{width},$info->{height});
}

sub list_files {
	debug sprintf("list_files('%s')",join("','",@_));
	my ($path,$regex) = @_;
	die "$path does not exist" unless -d $path;

	$regex = qr($regex);
	opendir(DH,$path) || die "Unable to open directory handle DH for directory '$path': $!\n";
	my @ary = grep { /$regex/i && -f "$path/$_" } readdir(DH);
	closedir(DH) || die "Unable to close directory handle DH for directory '$path': $!\n";

	my @readable = ();
	foreach (@ary) {
		# Only list readable files
		push @readable,$_ if (-f "$path/$_" && -r "$path/$_");
	}

	return @readable;
}

sub encode_url {
	debug sprintf("encode_url('%s')",join("','",@_));
	my $url = shift;
	$url =~ s/([^a-zA-Z0-9_.-])/uc sprintf("%%%02x",ord($1))/eg;
	return $url;
}

sub commify {
	debug sprintf("commify('%s')",join("','",@_));
	local $_  = shift;
	s/^\s+|\s+$//g;
	1 while s/^([-+]?\d+)(\d{3})/$1,$2/;
	return $_;
}

sub untaint {
	debug sprintf("untaint('%s')",join("','",@_));
	my $value = shift;
	if ($value =~ m/^(
			[\.\/][\(\)\[\]a-zA-Z0-9'\@\.\-\_ \/\+\!]+ |
			[\(\)\[\]a-zA-Z0-9'\@\.\-\_ \/\+\!]{2..} |
			[^\.\/]
		)$/x) {
		return $1;
	}
	die "untaint() Error: '$value' is tainted\n";
}

END {
	if ($DEBUG) {
		debug '------------------------------------------------------------';
		close(D) || warn "Unable to close file handle D for file '${MOI}_debug.log': $!\n";
	}
}

############################################################

__END__

=head1 NAME

gallery.cgi - Simple Image Gallery Script

=head1 SYNOPSIS

    <!--#exec cgi="/cgi-bin/gallery.cgi" -->

    http://perlguy.org.uk/cgi-bin/gallery.cgi?gallery=/perl_guy/photos

    http://perlguy.org.uk/perl_guy/photos/

=head1 DESCRIPTION

The File::Copy module provides two basic functions, C<copy> and
C<move>, which are useful for getting the contents of a file from
one place to another.

=head1 INSTALLATION

=head1 OPERATION

=head2 SSI

=head2 CGI

=head1 CONFIGURATION

=head2 Example

This is an example I<gallery.conf> file taken from http://perlguy.org.uk

    # Which images we'll display
    ImageMask "\.(jpe?g|tiff?|gif|png|JPE?G|GIF|TIFF?|mpe?g|MPE?G)"

    # Generic global options
    ThumbDir       thumbnails
    ThumbPrefix    _
    ThumbMaxDim    120
    ThumbQuality   99
    Rows           7
    Columns        4
    Overlay        frame.gif
    OverlayGravity Center
    CanvasColour   #D8D8B1
    CanvasWidth    82
    CanvasHeight   120
    Password       DeleteItDammit!

    # MPEG and AVI video options
    FilmColour       black
    FrameMaxDim      70
    MaxFrames        5

    # Custom picture galleries
    <Gallery /perl_guy/sentimental/care_bears/piccies/colouring_book>
        Rows         2
        Columns      2
        ThumbQuality 60
        ThumbMaxDim  200
        CanvasColour Off
        Overlay      Off
    </Gallery>

    <Gallery /amusing/dilbert>
        Title        Dilbert Archive
        Rows         3
        Columns      2
        ThumbMaxDim  200
        CanvasColour Off
        Overlay      Off
        Password     qwerty
    </Gallery>

    # Custom video galleries
    <Gallery /perl_guy/video_clips/my_rabbit_field>
        #ImageMask "\.(jpe?g|tiff?|gif|png|JPE?G|GIF|TIFF?)"
        Columns 2
        Rows 4
        ThumbMaxDim 145
        ThumbQuality 90
        FrameMaxDim  70
        MaxFrames    5
    </Gallery>

    <Gallery /perl_guy/video_clips>
        Columns 1
        Rows 4
        ThumbMaxDim 640
        ThumbQuality 90
    </Gallery>

=head2 Overview

I<gallery.cgi> is configured by placing L<directives|directives> in a plain text 
configuration file. The configuration file is usually called I<gallery.conf>. 
This file must be located in the same directory as the I<gallery.cgi> program 
itself. In addition, other configuration files may be added using the L<Include|include> 
directive. Any directive may be placed in any of these configuration files.

=head2 Directives

=head3 Include

=head3 ImageMask

=head3 ThumbDir

B<Syntax:> ThumbDir I<String>
B<Default:> C<ThumbDir thumbnails>
B<Context:> main config

See also L<HighResDir|highresdir>, L<ThumbPrefix|thumbprefix>, L<ThumbTemplate|thumbtemplate>, L<ThumbMaxDim|thumbmaxdim>, L<ThumbQuality|thumbquality>

=head3 ThumbPrefix

See also L<ThumbDir|thumbdir>, L<ThumbTemplate|thumbtemplate>, L<ThumbMaxDim|thumbmaxdim>, L<ThumbQuality|thumbquality>

=head3 ThumbMaxDim

See also L<ThumbDir|thumbdir>, L<ThumbPrefix|thumbprefix>, L<ThumbTemplate|thumbtemplate>, L<ThumbQuality|thumbquality>

=head3 ThumbQuality

See also L<ThumbDir|thumbdir>, L<ThumbPrefix|thumbprefix>, L<ThumbTemplate|thumbtemplate>, L<ThumbMaxDim|thumbmaxdim>

=head3 ThumbTemplate

See also L<ThumbDir|thumbdir>, L<ThumbPrefix|thumbprefix>, L<ThumbMaxDim|thumbmaxdim>, L<ThumbQuality|thumbquality>

=head3 HighResVersion

B<Syntax:> HighResVersion I<Boolean>
B<Default:> C<HighResVersion Off>
B<Context:> main config, gallery scope

See also L<HighResDir|highresdir>, L<HighResMinDim|highresmindim>, L<HighResPrefix|highresprefix>, L<LowResQuality|lowresquality>, L<LowResMaxDim|lowresmaxdim>

=head3 HighResMinDim

B<Syntax:> HighResMinDim I<Number>
B<Default:> C<HighResMinDim 641>
B<Context:> main config, gallery scope

See also L<HighResDir|highresdir>, L<HighResVersion|highresversion>, L<HighResPrefix|highresprefix>, L<LowResQuality|lowresquality>, L<LowResMaxDim|lowresmaxdim>

=head3 LowResMaxDim

See also L<HighResDir|highresdir>, L<HighResVersion|highresversion>, L<HighResPrefix|highresprefix>, L<LowResQuality|lowresquality>

=head3 LowResQuality

See also L<HighResDir|highresdir>, L<HighResVersion|highresversion>, L<HighResPrefix|highresprefix>, L<LowResMaxDim|lowresmaxdim>

=head3 HighResPrefix

B<Syntax:> HighResPrefix I<String>
B<Default:> C<HighResPrefix +>
B<Context:> main config

See also L<HighResMinDim|highresmindim>, L<HighResDir|highresdir>, L<HighResVersion|highresversion>, L<ThumbDir|thumbdir>, L<LowResQuality|lowresquality>, L<LowResMaxDim|lowresmaxdim>

=head3 HighResDir

B<Syntax:> HighResDir I<String>
B<Default:> C<HighResDir hires>
B<Context:> main config

See also L<HighResMinDim|highresmindim>, L<HighResVersion|highresversion>, L<HighResPrefix|highresprefix>, L<ThumbDir|thumbdir>, L<LowResQuality|lowresquality>, L<LowResMaxDim|lowresmaxdim>

=head3 Overlay

See also L<OverlayGravity|overlaygravity>

=head3 OverlayGravity

See also L<Overlay|overlay>

=head3 CanvasColour

See also L<CanvasWidth|canvaswidth>, L<CanvasHeight|canvasheight>

=head3 CanvasWidth

See also L<CanvasColour|canvascolour>, L<CanvasHeight|canvasheight>

=head3 CanvasHeight

See also L<CanvasColour|canvascolour>, L<CanvasWidth|canvaswidth>

=head3 FilmColour

See also L<FrameMaxDim|framemaxdim>, L<FrameSpacing|framespacing>, L<MaxFrames|maxframes>

=head3 FrameMaxDim

See also L<FilmColour|filmcolour>, L<FrameSpacing|framespacing>, L<MaxFrames|maxframes>

=head3 FrameSpacing

See also L<FilmColour|filmcolour>, L<FrameMaxDim|framemaxdim>, L<MaxFrames|maxframes>

=head3 MaxFrames

See also L<FilmColour|filmcolour>, L<FrameMaxDim|framemaxdim>, L<FrameSpacing|framespacing>

=head3 Rows

B<Syntax:> Rows I<Number>
B<Default:> C<Rows 5>
B<Context:> main config, gallery scope

Defines the maximum number of rows to be displayed per page of thumbnails.

See also L<Columns|columns>, L<PageQuickLinks|pagequicklinks>

=head3 Columns

B<Syntax:> Columns I<Number>
B<Default:> C<Columns 3>
B<Context:> main config, gallery scope

Defines the maximum number of columns to be displayed per page of thumbnails.

See also L<Rows|rows>, L<PageQuickLinks|pagequicklinks>

=head3 Title

B<Syntax:> Title I<String>
B<Context:> gallery scope

Defines the title of a gallery which may be displayed using  C<<!-- TMPL_VAR 
NAME=title -->> in the thumbnail or view template.

=head3 ImageTemplate

=head3 PageQuickLinks

See also L<Columns|columns>, L<Rows|rows>

=head3 Descriptions

=head3 Gallery

=head3 Password

=head3 Document_Root




=head1 TEMPLATES

=head2 gallery.cgi.tmpl

=head3 Example


=head2 gallery.cgi.view.tmpl

=head3 Example

    <center>
      <h2><!-- TMPL_IF NAME=title --><!-- TMPL_VAR NAME=title -->: <!-- TMPL_ELSE -->Untitled Gallery: <!-- /TMPL_IF --><!-- TMPL_VAR NAME=filename --></h2>
      <a href="javascript:history.back()"><img
        src="<!-- TMPL_VAR NAME=image_uri -->"
        width="<!-- TMPL_VAR NAME=image_width -->"
        height="<!-- TMPL_VAR NAME=image_height -->"
        border="1"
        alt="<!-- TMPL_VAR NAME=filename -->" /></a>
    </center><br />
    Filename: <!-- TMPL_VAR NAME=filename --><br />
    <!-- TMPL_IF NAME=description -->Description: <!-- TMPL_VAR NAME=description --><br /><!-- /TMPL_IF -->
    <!-- TMPL_IF NAME=image_width -->Dimensions: <!-- TMPL_VAR NAME=image_width --> x <!-- TMPL_VAR NAME=image_height -->
      <!-- TMPL_IF NAME=image_resolution -->(<!-- TMPL_VAR NAME=image_resolution -->)<!-- /TMPL_IF --><br><!-- /TMPL_IF -->
    <!-- TMPL_IF NAME=image_Comment -->Comment: <!-- TMPL_VAR NAME=image_Comment --><br /><!-- /TMPL_IF -->
    <!-- TMPL_IF NAME=image_LastModificationTime -->LastModificationTime: <!-- TMPL_VAR NAME=image_LastModificationTime --><!-- /TMPL_IF -->

=head1 BUGS

Hopefully none. :-) Send any bug reports to me at nicolaw@perlguy.org.uk along with 
any patches and details of how to replicate the problem. Please only send 
reports for bugs which can be replicated in the B<latest> version of the 
software. The latest version can always be found at 
http://www.nicolaworthington.com

=head1 AUTHOR

Nicola Worthongton <nicolaworthington@msn.com>

http://www.nicolaworthington.com

