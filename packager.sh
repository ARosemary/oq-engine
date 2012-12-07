#!/bin/sh

#
#  no gpg sign
#

set -x
set -e
GEM_BUILD_ROOT="build-deb"
GEM_BUILD_SRC="${GEM_BUILD_ROOT}/python-oq"

GEM_ALWAYS_YES=false

NL="
"
TB="	"

#
#  functions

mksafedir () {
    local dname

    dname="$1"
    if [ "$GEM_ALWAYS_YES" != "true" -a -d "$dname" ]; then
        echo "$dname already exists"
        echo "press Enter to continue or CTRL+C to abort"
        read a
    fi
    rm -rf $dname
    mkdir -p $dname
}

usage () {
    local ret

    ret=$1

    echo
    echo "USAGE:"
    echo "    $0 [-D|--development] [-B|--binaries] [-U|--unsigned]    build debian source package."
    echo "       if -B argument is present binary package is build too."
    echo "       if -D argument is present a package with self-computed version is produced."
    echo "       if -U argoment is present no sign are perfomed using gpg key related to the mantainer."
    echo "    $0 pkgtest <last-ip-digit>                  run tests into an ubuntu lxc environment"
    echo
    exit $ret
}

pkgtest_run () {
    local le_addr="$1" haddr

    #
    #  check if an istance with the same address already exists
    export haddr="10.0.3.$le_addr"
    if sudo sh -c "grep -q \"[^#]*address[ 	]\+$haddr[ 	]*$\" /var/lib/lxc/ubuntu-lxc-*/rootfs/etc/network/interfaces >/dev/null 2>&1"; then
        echo "The $haddr machine seems to be already configured"
        return 1
    fi

    #
    #  run build of package
    if [ -d build-deb ]; then
        if [ ! -f build-deb/python-oq*.deb ]; then
            echo "'build-deb' directory already exists but .deb file package was not found"
            return 1

        fi
    else
        $0 -D -B -U
    fi

    #
    #  run the VM and get the VM name
    sudo lxc-start-ephemeral-gem -i $le_addr -d -o ubuntu-lxc >${haddr}.lxc.log 2>&1

    #
    #  prepare repo and install python-oq package
    cd build-deb
    dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz
    dpkg-scansources . | gzip > Sources.gz
    cd -

    # waiting VM startup
    for i in $(seq 1 60); do
        if ssh $haddr "echo VM Running" 2>/dev/null; then
            lxc-ls | tail -n +2
            machine_name="$(grep "is running" ${haddr}.lxc.log | sed 's/ is running.*//g')"
            echo "MACHINE NAME: [$machine_name]"
            break
        fi
        sleep 1
    done
    if [ $i -eq 60 ]; then
        echo "VM not responding"
        return 2
    fi

    # install package to manage repository properly
    ssh $haddr "sudo apt-get install python-software-properties"

    # create a remote "local repo" where place python-oq package
    ssh $haddr mkdir repo
    scp build-deb/python-oq_*.deb build-deb/Packages.gz  build-deb/Sources.gz $haddr:repo
    ssh $haddr "sudo apt-add-repository \"deb file:/home/ubuntu/repo ./\""
    ssh $haddr "sudo apt-get update"

    # packaging related tests (install, remove, purge, install, reinstall)
    ssh $haddr "sudo apt-get install --force-yes -y python-oq"
    ssh $haddr "sudo apt-get remove --force-yes -y python-oq"
    ssh $haddr "sudo apt-get install --force-yes -y python-oq"
    ssh $haddr "sudo apt-get install --reinstall --force-yes -y python-oq"

    sudo lxc-shutdown -n $machine_name -w -t 10

    # app related tests (run demos)
    # TODO

}

#
#  MAIN
#
BUILD_BINARIES=0
BUILD_DEVEL=0
BUILD_UNSIGN=0
#  args management
while [ $# -gt 0 ]; do
    case $1 in
        -D|--development)
            BUILD_DEVEL=1
            if [ "$DEBFULLNAME" = "" -o "$DEBEMAIL" = "" ]; then
                echo
                echo "error: set DEBFULLNAME and DEBEMAIL environment vars and run again the script"
                echo
                exit 1
            fi
            ;;
        -B|--binaries)
            BUILD_BINARIES=1
            ;;
        -U|--unsigned)
            BUILD_UNSIGN=1
            ;;
        -h|--help)
            usage 0
            break
            ;;
        pkgtest)
            pkgtest_run $2
            return $?
            break
            ;;
        *)
            usage 1
            break
            ;;
    esac
    shift
done

DPBP_FLAG=""
if [ $BUILD_BINARIES -eq 0 ]; then
    DPBP_FLAG="-S"
fi
if [ $BUILD_UNSIGN -eq 1 ]; then
    DPBP_FLAG="$DPBP_FLAG -us -uc"
fi

mksafedir "$GEM_BUILD_ROOT"
mksafedir "$GEM_BUILD_SRC"

git archive HEAD | (cd "$GEM_BUILD_SRC" ; tar xv)

# NOTE: if in the future we need modules we need to execute the following commands
# 
# git submodule init
# git submodule update
##  "submodule foreach" vars: $name, $path, $sha1 and $toplevel:
# git submodule foreach "git archive HEAD | (cd \"\${toplevel}/${GEM_BUILD_SRC}/\$path\" ; tar xv ) "

cd "$GEM_BUILD_SRC"

# date
dt="$(date +%s)"

# version from setup.py
stp_vers="$(cat setup.py | grep '^[ 	]*version=' | sed -n 's/^[ 	]*version="//g;s/".*//gp')"
stp_maj="$(echo "$stp_vers" | sed -n 's/^\([0-9]\+\).*/\1/gp')"
stp_min="$(echo "$stp_vers" | sed -n 's/^[0-9]\+\.\([0-9]\+\).*/\1/gp')"
stp_bfx="$(echo "$stp_vers" | sed -n 's/^[0-9]\+\.[0-9]\+\.\([0-9]\+\).*/\1/gp')"
stp_suf="$(echo "$stp_vers" | sed -n 's/^[0-9]\+\.[0-9]\+\.[0-9]\+\(.*\)/\1/gp')"
# echo "stp [$stp_vers] [$stp_maj] [$stp_min] [$stp_bfx] [$stp_suf]"

# version info from openquake/__init__.py
ini_maj="$(cat openquake/__init__.py | grep '# major' | sed -n 's/^[ ]*//g;s/,.*//gp')"
ini_min="$(cat openquake/__init__.py | grep '# minor' | sed -n 's/^[ ]*//g;s/,.*//gp')"
ini_bfx="$(cat openquake/__init__.py | grep '# sprint number' | sed -n 's/^[ ]*//g;s/,.*//gp')"
ini_suf="" # currently not included into the version array structure
# echo "ini [] [$ini_maj] [$ini_min] [$ini_bfx] [$ini_suf]"

# version info from debian/changelog
h="$(head -n1 debian/changelog)"
# pkg_vers="$(echo "$h" | cut -d ' ' -f 2 | cut -d '(' -f 2 | cut -d ')' -f 1 | sed -n 's/[-+].*//gp')"
pkg_name="$(echo "$h" | cut -d ' ' -f 1)"
pkg_vers="$(echo "$h" | cut -d ' ' -f 2 | cut -d '(' -f 2 | cut -d ')' -f 1)"
pkg_rest="$(echo "$h" | cut -d ' ' -f 3-)"
pkg_maj="$(echo "$pkg_vers" | sed -n 's/^\([0-9]\+\).*/\1/gp')"
pkg_min="$(echo "$pkg_vers" | sed -n 's/^[0-9]\+\.\([0-9]\+\).*/\1/gp')"
pkg_bfx="$(echo "$pkg_vers" | sed -n 's/^[0-9]\+\.[0-9]\+\.\([0-9]\+\).*/\1/gp')"
pkg_deb="$(echo "$pkg_vers" | sed -n 's/^[0-9]\+\.[0-9]\+\.[0-9]\+\(-[^+]\+\).*/\1/gp')"
pkg_suf="$(echo "$pkg_vers" | sed -n 's/^[0-9]\+\.[0-9]\+\.[0-9]\+-[^+]\+\(+.*\)/\1/gp')"
# echo "pkg [$pkg_vers] [$pkg_maj] [$pkg_min] [$pkg_bfx] [$pkg_deb] [$pkg_suf]"

if [ $BUILD_DEVEL -eq 1 ]; then
    hash="$(git log --pretty='format:%h' -1)"
    mv debian/changelog debian/changelog.orig

    if [ "$pkg_maj" = "$ini_maj" -a "$pkg_min" = "$ini_min" -a \
         "$pkg_bfx" = "$ini_bfx" -a "$pkg_deb" != "" ]; then
        deb_ct="$(echo "$pkg_deb" | sed 's/^-//g')"
        pkg_deb="-$(( deb_ct + 1 ))"
    else
        pkg_maj="$ini_maj"
        pkg_min="$ini_min"
        pkg_bfx="$ini_bfx"
        pkg_deb="-1"
    fi

    ( echo "$pkg_name (${pkg_maj}.${pkg_min}.${pkg_bfx}${pkg_deb}+dev${dt}-${hash}) $pkg_rest"
      echo
      echo "  *  development version from $hash commit"
      echo
      echo " -- $DEBFULLNAME <$DEBEMAIL>  $(date -d@$dt -R)"
      echo
    )  > debian/changelog
    cat debian/changelog.orig >> debian/changelog
    rm debian/changelog.orig
fi

if [  "$ini_maj" != "$pkg_maj" -o "$ini_maj" != "$stp_maj" -o \
      "$ini_min" != "$pkg_min" -o "$ini_min" != "$stp_min" -o \
      "$ini_bfx" != "$pkg_bfx" -o "$ini_bfx" != "$stp_bfx" ]; then
    echo
    echo "Versions are not aligned"
    echo "    init:  ${ini_maj}.${ini_min}.${ini_bfx}"
    echo "    setup: ${stp_maj}.${stp_min}.${stp_bfx}"
    echo "    pkg:   ${pkg_maj}.${pkg_min}.${pkg_bfx}"
    echo
    echo "press [enter] to continue, [ctrl+c] to abort"
    read a
fi

sed -i "s/^\([ 	]*\)[^)]*\()  # release date .*\)/\1${dt}\2/g" openquake/__init__.py

# mods pre-packaging
mv LICENSE         openquake
mv README.txt      openquake/README
mv celeryconfig.py openquake
mv openquake.cfg   openquake

mv bin/openquake   bin/oqscript.py
mv bin             openquake/bin

rm -rf $(find demos -mindepth 1 -maxdepth 1 | egrep -v 'demos/simple_fault_demo_hazard|demos/event_based_hazard|demos/_site_model')
dpkg-buildpackage $DPBP_FLAG
cd -

if [ $BUILD_DEVEL -ne 1 ]; then
    exit 0
fi

#
# DEVEL EXTRACTION OF SOURCES
if [ -z "$GEM_SRC_PKG" ]; then
    echo "env var GEM_SRC_PKG not set, exit"
    exit 0
fi
GEM_BUILD_PKG="${GEM_SRC_PKG}/pkg"
mksafedir "$GEM_BUILD_PKG"
GEM_BUILD_EXTR="${GEM_SRC_PKG}/extr"
mksafedir "$GEM_BUILD_EXTR"
cp  ${GEM_BUILD_ROOT}/python-oq_*.deb  $GEM_BUILD_PKG
cd "$GEM_BUILD_EXTR"
dpkg -x $GEM_BUILD_PKG/python-oq_*.deb .
dpkg -e $GEM_BUILD_PKG/python-oq_*.deb
