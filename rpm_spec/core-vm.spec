#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2010  Joanna Rutkowska <joanna@invisiblethingslab.com>
# Copyright (C) 2010  Rafal Wojtczuk  <rafal@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#

%{!?version: %define version %(cat version)}
%{!?backend_vmm: %define backend_vmm %(echo $BACKEND_VMM)}

Name:		qubes-core-vm
Version:	%{version}
Release:	1%{dist}
Summary:	The Qubes core files for VM

Group:		Qubes
Vendor:		Invisible Things Lab
License:	GPL
URL:		http://www.qubes-os.org
Requires:   fedora-release
%if %{fedora} < 22
Requires:   yum-plugin-post-transaction-actions
%endif
Requires:   NetworkManager >= 0.8.1-1
%if %{fedora} >= 18
# Fedora >= 18 defaults to firewalld, which isn't supported nor needed by Qubes
Conflicts:  firewalld
%endif
Requires:	xdg-utils
Requires:   ethtool
Requires:   tinyproxy
Requires:   ntpdate
Requires:   net-tools
Requires:   nautilus-python
Requires:   qubes-utils >= 3.1.3
Requires:   initscripts
# for qubes-desktop-run
Requires:   pygobject3-base
Requires:   dbus-python
# for qubes-session-autostart, xdg-icon
Requires:   pyxdg
%if %{fedora} >= 20
# gpk-update-viewer required by qubes-manager
Requires:   gnome-packagekit-updater
%endif
Requires:   ImageMagick
Requires:   librsvg2-tools
Requires:   fakeroot
Requires:   desktop-notification-daemon
# to show/hide nm-applet
Requires:   dconf
Requires:   pygtk2
Requires:   zenity
Requires:   qubes-libvchan
Requires:   qubes-db-vm
%if 0%{fedora} >= 23
Requires:   python3-dnf-plugins-qubes-hooks
%else
Requires:   python2-dnf-plugins-qubes-hooks
%endif
Obsoletes:  qubes-core-vm-kernel-placeholder <= 1.0
Obsoletes:  qubes-upgrade-vm < 3.1
BuildRequires: xen-devel
BuildRequires: libX11-devel
BuildRequires: qubes-utils-devel >= 3.1.3
BuildRequires: qubes-libvchan-%{backend_vmm}-devel

%package -n python2-dnf-plugins-qubes-hooks
Summary:	DNF plugin for Qubes specific post-installation actions
BuildRequires: python2-devel
%{?python_provide:%python_provide python2-dnf-plugins-qubes-hooks}

%description -n python2-dnf-plugins-qubes-hooks
DNF plugin for Qubes specific post-installation actions:
 * notify dom0 that updates were installed
 * refresh applications shortcut list

%package -n python3-dnf-plugins-qubes-hooks
Summary:	DNF plugin for Qubes specific post-installation actions
BuildRequires: python3-devel
%{?python_provide:%python_provide python3-dnf-plugins-qubes-hooks}

%description -n python3-dnf-plugins-qubes-hooks
DNF plugin for Qubes specific post-installation actions:
 * notify dom0 that updates were installed
 * refresh applications shortcut list

%define _builddir %(pwd)

%define kde_service_dir /usr/share/kde4/services

%description
The Qubes core files for installation inside a Qubes VM.

%prep
# we operate on the current directory, so no need to unpack anything
# symlink is to generate useful debuginfo packages
rm -f %{name}-%{version}
ln -sf . %{name}-%{version}
%setup -T -D

%build
for dir in qubes-rpc qrexec misc; do
  (cd $dir; make)
done

%pre
# Make sure there is a qubes group
groupadd --force --system --gid 98 qubes
id -u 'user' >/dev/null 2>&1 || {
  useradd --user-group --create-home --shell /bin/bash user
}
usermod -a --groups qubes user

if [ "$1" !=  1 ] ; then
# do this whole %%pre thing only when updating for the first time...
exit 0
fi

mkdir -p /var/lib/qubes
if [ -e /etc/fstab ] ; then
mv /etc/fstab /var/lib/qubes/fstab.orig
fi

usermod -p '' root
usermod -L user

%install

(cd qrexec; make install DESTDIR=$RPM_BUILD_ROOT)
make install-vm DESTDIR=$RPM_BUILD_ROOT

%if %{fedora} >= 22
rm -f $RPM_BUILD_ROOT/etc/yum/post-actions/qubes-trigger-sync-appmenus.action
%endif

%triggerin -- initscripts
if [ -e /etc/init/serial.conf ]; then
	cp /usr/share/qubes/serial.conf /etc/init/serial.conf
fi

%post

# disable some Upstart services
for F in plymouth-shutdown prefdm splash-manager start-ttys tty ; do
	if [ -e /etc/init/$F.conf ]; then
		mv -f /etc/init/$F.conf /etc/init/$F.conf.disabled
	fi
done

# Create NetworkManager configuration if we do not have it
if ! [ -e /etc/NetworkManager/NetworkManager.conf ]; then
echo '[main]' > /etc/NetworkManager/NetworkManager.conf
echo 'plugins = keyfile' >> /etc/NetworkManager/NetworkManager.conf
echo '[keyfile]' >> /etc/NetworkManager/NetworkManager.conf
fi
/usr/lib/qubes/qubes-fix-nm-conf.sh


# Remove ip_forward setting from sysctl, so NM will not reset it
sed 's/^net.ipv4.ip_forward.*/#\0/'  -i /etc/sysctl.conf

# Remove old firmware updates link
if [ -L /lib/firmware/updates ]; then
  rm -f /lib/firmware/updates
fi

if ! grep -q '/etc/yum\.conf\.d/qubes-proxy\.conf' /etc/yum.conf; then
  echo >> /etc/yum.conf
  echo '# Yum does not support inclusion of config dir...' >> /etc/yum.conf
  echo 'include=file:///etc/yum.conf.d/qubes-proxy.conf' >> /etc/yum.conf
fi

# And actually setup the proxy usage in package managers
/usr/lib/qubes/update-proxy-configs

# Location of files which contains list of protected files
mkdir -p /etc/qubes/protected-files.d
PROTECTED_FILE_LIST='/etc/qubes/protected-files.d'

# qubes-core-vm has been broken for some time - it overrides /etc/hosts; restore original content
if ! grep -rq "^/etc/hosts$" "${PROTECTED_FILE_LIST}" 2>/dev/null; then
    if ! grep -q localhost /etc/hosts; then
      cat <<EOF > /etc/hosts
127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4 `hostname`
::1         localhost localhost.localdomain localhost6 localhost6.localdomain6
EOF
    fi
fi

# ensure that hostname resolves to 127.0.0.1 resp. ::1 and that /etc/hosts is
# in the form expected by qubes-sysinit.sh
if ! grep -rq "^/etc/hostname$" "${PROTECTED_FILE_LIST}" 2>/dev/null; then
    for ip in '127\.0\.0\.1' '::1'; do
        if grep -q "^${ip}\(\s\|$\)" /etc/hosts; then
            sed -i "/^${ip}\s/,+0s/\(\s`hostname`\)\+\(\s\|$\)/\2/g" /etc/hosts
            sed -i "s/^${ip}\(\s\|$\).*$/\0 `hostname`/" /etc/hosts
        else
            echo "${ip} `hostname`" >> /etc/hosts
        fi
    done
fi

%if %{fedora} >= 20
# Make sure there is a default locale set so gnome-terminal will start
if [ ! -e /etc/locale.conf ] || ! grep -q LANG /etc/locale.conf; then
    touch /etc/locale.conf
    echo "LANG=en_US.UTF-8" >> /etc/locale.conf
fi
# ... and make sure it is really generated
current_locale=`grep LANG /etc/locale.conf|cut -f 2 -d = | tr -d '"'`
if [ -n "$current_locale" ] && ! locale -a | grep -q "$current_locale"; then
    base=`echo "$current_locale" | cut -f 1 -d .`
    charmap=`echo "$current_locale.UTF-8" | cut -f 2 -d .`
    [ -n "$charmap" ] && charmap="-f $charmap"
    localedef -i $base $charmap $current_locale
fi
%endif

if [ "$1" !=  1 ] ; then
# do the rest of %%post thing only when updating for the first time...
exit 0
fi

if [ -e /etc/init/serial.conf ] && ! [ -f /var/lib/qubes/serial.orig ] ; then
	cp /etc/init/serial.conf /var/lib/qubes/serial.orig
fi

# Remove most of the udev scripts to speed up the VM boot time
# Just leave the xen* scripts, that are needed if this VM was
# ever used as a net backend (e.g. as a VPN domain in the future)
#echo "--> Removing unnecessary udev scripts..."
mkdir -p /var/lib/qubes/removed-udev-scripts
for f in /etc/udev/rules.d/*
do
    if [ $(basename $f) == "xen-backend.rules" ] ; then
        continue
    fi

    if [ $(basename $f) == "50-qubes-misc.rules" ] ; then
        continue
    fi

    if echo $f | grep -q qubes; then
        continue
    fi

    mv $f /var/lib/qubes/removed-udev-scripts/
done
mkdir -p /rw

#rm -f /etc/mtab
#echo "--> Removing HWADDR setting from /etc/sysconfig/network-scripts/ifcfg-eth0"
#mv /etc/sysconfig/network-scripts/ifcfg-eth0 /etc/sysconfig/network-scripts/ifcfg-eth0.orig
#grep -v HWADDR /etc/sysconfig/network-scripts/ifcfg-eth0.orig > /etc/sysconfig/network-scripts/ifcfg-eth0

%triggerin -- notification-daemon
# Enable autostart of notification-daemon when installed
if [ ! -e /etc/xdg/autostart/notification-daemon.desktop ]; then
    ln -s /usr/share/applications/notification-daemon.desktop /etc/xdg/autostart/
fi
exit 0

%triggerin -- selinux-policy
#echo "--> Disabling SELinux..."
sed -e s/^SELINUX=.*$/SELINUX=disabled/ </etc/selinux/config >/etc/selinux/config.processed
mv /etc/selinux/config.processed /etc/selinux/config
setenforce 0 2>/dev/null
exit 0

%preun
if [ "$1" = 0 ] ; then
    # no more packages left
    if [ -e /var/lib/qubes/fstab.orig ] ; then
    mv /var/lib/qubes/fstab.orig /etc/fstab
    fi
    mv /var/lib/qubes/removed-udev-scripts/* /etc/udev/rules.d/
    if [ -e /var/lib/qubes/serial.orig ] ; then
    mv /var/lib/qubes/serial.orig /etc/init/serial.conf
    fi
fi

%postun
if [ $1 -eq 0 ] ; then
    /usr/bin/glib-compile-schemas %{_datadir}/glib-2.0/schemas &> /dev/null || :

    if [ -L /lib/firmware/updates ]; then
      rm /lib/firmware/updates
    fi

    rm -rf /var/lib/qubes/xdg
fi

%posttrans
    /usr/bin/glib-compile-schemas %{_datadir}/glib-2.0/schemas &> /dev/null || :

%clean
rm -rf $RPM_BUILD_ROOT
rm -f %{name}-%{version}

%files
%defattr(-,root,root,-)
%dir /var/lib/qubes
%dir /var/run/qubes
%dir %attr(0775,user,user) /var/lib/qubes/dom0-updates
%{kde_service_dir}/qvm-copy.desktop
%{kde_service_dir}/qvm-move.desktop
%{kde_service_dir}/qvm-dvm.desktop
/etc/NetworkManager/dispatcher.d/30-qubes-external-ip
/etc/NetworkManager/dispatcher.d/qubes-nmhook
%config(noreplace) /etc/X11/xorg-preload-apps.conf
/etc/dispvm-dotfiles.tbz
/etc/dhclient.d/qubes-setup-dnat-to-ns.sh
/etc/fstab
/etc/pki/rpm-gpg/RPM-GPG-KEY-qubes*
%config(noreplace) /etc/polkit-1/localauthority/50-local.d/qubes-allow-all.pkla
%config(noreplace) /etc/polkit-1/rules.d/00-qubes-allow-all.rules
%dir /etc/qubes-rpc
%config(noreplace) /etc/qubes-rpc/qubes.Filecopy
%config(noreplace) /etc/qubes-rpc/qubes.OpenInVM
%config(noreplace) /etc/qubes-rpc/qubes.GetAppmenus
%config(noreplace) /etc/qubes-rpc/qubes.VMShell
%config(noreplace) /etc/qubes-rpc/qubes.SyncNtpClock
%config(noreplace) /etc/qubes-rpc/qubes.SuspendPre
%config(noreplace) /etc/qubes-rpc/qubes.SuspendPost
%config(noreplace) /etc/qubes-rpc/qubes.WaitForSession
%config(noreplace) /etc/qubes-rpc/qubes.DetachPciDevice
%config(noreplace) /etc/qubes-rpc/qubes.Backup
%config(noreplace) /etc/qubes-rpc/qubes.Restore
%config(noreplace) /etc/qubes-rpc/qubes.SelectFile
%config(noreplace) /etc/qubes-rpc/qubes.SelectDirectory
%config(noreplace) /etc/qubes-rpc/qubes.GetImageRGBA
%config(noreplace) /etc/qubes-rpc/qubes.SetDateTime
%config(noreplace) /etc/qubes-rpc/qubes.InstallUpdatesGUI
%dir /etc/qubes/autostart
/etc/qubes/autostart/README.txt
%config /etc/qubes/autostart/*.desktop.d/30_qubes.conf
%config(noreplace) /etc/sudoers.d/qubes
%config(noreplace) /etc/sudoers.d/qt_x11_no_mitshm
%config(noreplace) /etc/sysctl.d/20_tcp_timestamps.conf
%config(noreplace) /etc/qubes/iptables.rules
%config(noreplace) /etc/qubes/ip6tables.rules
%config(noreplace) /etc/tinyproxy/tinyproxy-updates.conf
%config(noreplace) /etc/tinyproxy/updates-blacklist
%config(noreplace) /etc/udev/rules.d/50-qubes-misc.rules
%config(noreplace) /etc/udev/rules.d/99-qubes-network.rules
%config(noreplace) /etc/qubes-suspend-module-blacklist
/etc/xdg/autostart/00-qubes-show-hide-nm-applet.desktop
/etc/xen/scripts/vif-route-qubes
%config(noreplace) /etc/yum.conf.d/qubes-proxy.conf
%config(noreplace) /etc/yum.repos.d/qubes-r3.repo
/etc/yum/pluginconf.d/yum-qubes-hooks.conf
%config(noreplace) /etc/dnf/plugins/qubes-hooks.conf
%if %{fedora} < 22
/etc/yum/post-actions/qubes-trigger-sync-appmenus.action
%endif
/usr/lib/systemd/system/user@.service.d/90-session-stop-timeout.conf
/usr/sbin/qubes-serial-login
/usr/bin/qvm-copy-to-vm
/usr/bin/qvm-move-to-vm
/usr/bin/qvm-open-in-dvm
/usr/bin/qvm-open-in-vm
/usr/bin/qvm-run
/usr/bin/qvm-mru-entry
/usr/bin/xenstore-watch-qubes
/usr/bin/qubes-desktop-run
/usr/bin/qubes-open
/usr/bin/qrexec-fork-server
/usr/bin/qrexec-client-vm
/usr/bin/qubes-session-autostart
%dir /usr/lib/qubes
/usr/lib/qubes/vusb-ctl.py*
/usr/lib/qubes/dispvm-prerun.sh
/usr/lib/qubes/sync-ntp-clock
/usr/lib/qubes/prepare-suspend
/usr/lib/qubes/network-manager-prepare-conf-dir
/usr/lib/qubes/show-hide-nm-applet.sh
/usr/lib/qubes/qrexec-agent
/usr/lib/qubes/qrexec-client-vm
/usr/lib/qubes/qrexec_client_vm
/usr/lib/qubes/qubes-rpc-multiplexer
/usr/lib/qubes/qfile-agent
%attr(4755,root,root) /usr/lib/qubes/qfile-unpacker
/usr/lib/qubes/qopen-in-vm
/usr/lib/qubes/qrun-in-vm
/usr/lib/qubes/qubes-download-dom0-updates.sh
/usr/lib/qubes/qubes-fix-nm-conf.sh
/usr/lib/qubes/qubes-setup-dnat-to-ns
/usr/lib/qubes/qubes-trigger-sync-appmenus.sh
/usr/lib/qubes/qvm-copy-to-vm.gnome
/usr/lib/qubes/qvm-copy-to-vm.kde
/usr/lib/qubes/qvm-move-to-vm.gnome
/usr/lib/qubes/qvm-move-to-vm.kde
/usr/lib/qubes/setup-ip
/usr/lib/qubes/tar2qfile
/usr/lib/qubes/vm-file-editor
/usr/lib/qubes/wrap-in-html-if-url.sh
/usr/lib/qubes/iptables-updates-proxy
/usr/lib/qubes/close-window
/usr/lib/qubes/xdg-icon
/usr/lib/qubes/update-proxy-configs
/usr/lib/qubes/upgrades-installed-check
/usr/lib/qubes/upgrades-status-notify
/usr/lib/yum-plugins/yum-qubes-hooks.py*
/usr/lib/dracut/dracut.conf.d/30-qubes.conf
/usr/lib64/python2.7/site-packages/qubes/xdg.py*
/usr/sbin/qubes-firewall
/usr/sbin/qubes-netwatcher
/usr/share/qubes/serial.conf
/usr/share/glib-2.0/schemas/org.gnome.settings-daemon.plugins.updates.gschema.override
/usr/share/glib-2.0/schemas/org.gnome.nautilus.gschema.override
/usr/share/glib-2.0/schemas/org.mate.NotificationDaemon.gschema.override
/usr/share/nautilus-python/extensions/qvm_copy_nautilus.py*
/usr/share/nautilus-python/extensions/qvm_move_nautilus.py*
/usr/share/nautilus-python/extensions/qvm_dvm_nautilus.py*

/usr/share/qubes/mime-override/globs
%dir /home_volatile
%attr(700,user,user) /home_volatile/user
%dir /mnt/removable
%dir /rw

%files -n python2-dnf-plugins-qubes-hooks
%{python2_sitelib}/dnf-plugins/*

%files -n python3-dnf-plugins-qubes-hooks
%{python3_sitelib}/dnf-plugins/*

%package sysvinit
Summary:        Qubes unit files for SysV init style or upstart
License:        GPL v2 only
Group:          Qubes
Requires:       upstart
Requires:       qubes-core-vm
Provides:       qubes-core-vm-init-scripts
Conflicts:      qubes-core-vm-systemd

%description sysvinit
The Qubes core startup configuration for SysV init (or upstart).

%files sysvinit
/etc/init.d/qubes-core
/etc/init.d/qubes-core-appvm
/etc/init.d/qubes-core-netvm
/etc/init.d/qubes-firewall
/etc/init.d/qubes-netwatcher
/etc/init.d/qubes-iptables
/etc/init.d/qubes-updates-proxy
/etc/init.d/qubes-qrexec-agent
/etc/sysconfig/modules/qubes-core.modules
/etc/sysconfig/modules/qubes-misc.modules

%post sysvinit

#echo "--> Turning off unnecessary services..."
# FIXME: perhaps there is more elegant way to do this?
for f in /etc/init.d/*
do
        srv=`basename $f`
        [ $srv = 'functions' ] && continue
        [ $srv = 'killall' ] && continue
        [ $srv = 'halt' ] && continue
        [ $srv = 'single' ] && continue
        [ $srv = 'reboot' ] && continue
        [ $srv = 'qubes-gui' ] && continue
        chkconfig $srv off
done

#echo "--> Enabling essential services..."
chkconfig rsyslog on
chkconfig haldaemon on
chkconfig messagebus on
chkconfig --add qubes-core || echo "WARNING: Cannot add service qubes-core!"
chkconfig qubes-core on || echo "WARNING: Cannot enable service qubes-core!"
chkconfig --add qubes-core-netvm || echo "WARNING: Cannot add service qubes-core-netvm!"
chkconfig qubes-core-netvm on || echo "WARNING: Cannot enable service qubes-core-netvm!"
chkconfig --add qubes-core-appvm || echo "WARNING: Cannot add service qubes-core-appvm!"
chkconfig qubes-core-appvm on || echo "WARNING: Cannot enable service qubes-core-appvm!"
chkconfig --add qubes-firewall || echo "WARNING: Cannot add service qubes-firewall!"
chkconfig qubes-firewall on || echo "WARNING: Cannot enable service qubes-firewall!"
chkconfig --add qubes-netwatcher || echo "WARNING: Cannot add service qubes-netwatcher!"
chkconfig qubes-netwatcher on || echo "WARNING: Cannot enable service qubes-netwatcher!"
chkconfig --add qubes-iptables || echo "WARNING: Cannot add service qubes-iptables!"
chkconfig qubes-iptables on || echo "WARNING: Cannot enable service qubes-iptables!"
chkconfig --add qubes-updates-proxy || echo "WARNING: Cannot add service qubes-updates-proxy!"
chkconfig qubes-updates-proxy on || echo "WARNING: Cannot enable service qubes-updates-proxy!"
chkconfig --add qubes-qrexec-agent || echo "WARNING: Cannot add service qubes-qrexec-agent!"
chkconfig qubes-qrexec-agent on || echo "WARNING: Cannot enable service qubes-qrexec-agent!"

# TODO: make this not display the silly message about security context...
sed -i s/^id:.:initdefault:/id:3:initdefault:/ /etc/inittab

%preun sysvinit
if [ "$1" = 0 ] ; then
    # no more packages left
    chkconfig qubes-core off
    chkconfig qubes-core-netvm off
    chkconfig qubes-core-appvm off
    chkconfig qubes-firewall off
    chkconfig qubes-netwatcher off
    chkconfig qubes-updates-proxy off
    chkconfig qubes-qrexec-agent off
fi

%package systemd
Summary:        Qubes unit files for SystemD init style
License:        GPL v2 only
Group:          Qubes
Requires:       systemd
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
Requires:       qubes-core-vm
Provides:       qubes-core-vm-init-scripts
Conflicts:      qubes-core-vm-sysvinit

%description systemd
The Qubes core startup configuration for SystemD init.

%files systemd
%defattr(-,root,root,-)
/lib/systemd/system/qubes-dvm.service
/lib/systemd/system/qubes-misc-post.service
/lib/systemd/system/qubes-firewall.service
/lib/systemd/system/qubes-mount-dirs.service
/lib/systemd/system/qubes-netwatcher.service
/lib/systemd/system/qubes-network.service
/lib/systemd/system/qubes-iptables.service
/lib/systemd/system/qubes-sysinit.service
/lib/systemd/system/qubes-update-check.service
/lib/systemd/system/qubes-update-check.timer
/lib/systemd/system/qubes-updates-proxy.service
/lib/systemd/system/qubes-qrexec-agent.service
/lib/systemd/system/qubes-random-seed.service
/lib/systemd/system-preset/75-qubes-vm.preset
/lib/modules-load.d/qubes-core.conf
/lib/modules-load.d/qubes-misc.conf
%dir /usr/lib/qubes/init
/usr/lib/qubes/init/prepare-dvm.sh
/usr/lib/qubes/init/network-proxy-setup.sh
/usr/lib/qubes/init/qubes-iptables
/usr/lib/qubes/init/misc-post.sh
/usr/lib/qubes/init/misc-post-stop.sh
/usr/lib/qubes/init/mount-dirs.sh
/usr/lib/qubes/init/qubes-random-seed.sh
/usr/lib/qubes/init/qubes-sysinit.sh
/lib/systemd/system/chronyd.service.d/30_qubes.conf
/lib/systemd/system/crond.service.d/30_qubes.conf
/lib/systemd/system/cups.service.d/30_qubes.conf
/lib/systemd/system/cups.socket.d/30_qubes.conf
/lib/systemd/system/cups.path.d/30_qubes.conf
/lib/systemd/system/org.cups.cupsd.service.d/30_qubes.conf
/lib/systemd/system/org.cups.cupsd.socket.d/30_qubes.conf
/lib/systemd/system/org.cups.cupsd.path.d/30_qubes.conf
/lib/systemd/system/getty@tty.service.d/30_qubes.conf
/lib/systemd/system/ModemManager.service.d/30_qubes.conf
/lib/systemd/system/NetworkManager.service.d/30_qubes.conf
/lib/systemd/system/NetworkManager-wait-online.service.d/30_qubes.conf
/lib/systemd/system/ntpd.service.d/30_qubes.conf
/lib/systemd/system/tinyproxy.service.d/30_not_needed_in_qubes_by_default.conf
/lib/systemd/system/tmp.mount.d/30_qubes.conf
/lib/systemd/user/pulseaudio.service.d/30_qubes.conf
/lib/systemd/user/pulseaudio.socket.d/30_qubes.conf
/usr/lib/tmpfiles.d/qubes-core-agent-linux.conf

%post systemd

PRESET_FAILED=0
if [ $1 -eq 1 ]; then
    /bin/systemctl --no-reload preset-all > /dev/null 2>&1 && PRESET_FAILED=0 || PRESET_FAILED=1
else
    services="qubes-dvm qubes-misc-post qubes-firewall qubes-mount-dirs"
    services="$services qubes-netwatcher qubes-network qubes-sysinit"
    services="$services qubes-iptables qubes-updates-proxy qubes-qrexec-agent"
    services="$services qubes-random-seed"
    for srv in $services; do
        /bin/systemctl --no-reload preset $srv.service
    done
    /bin/systemctl --no-reload preset qubes-update-check.timer
    # Upgrade path - now qubes-iptables is used instead
    /bin/systemctl --no-reload preset iptables.service
    /bin/systemctl --no-reload preset ip6tables.service
fi

# Set default "runlevel"
rm -f /etc/systemd/system/default.target
ln -s /lib/systemd/system/multi-user.target /etc/systemd/system/default.target

grep '^[[:space:]]*[^#;]' /lib/systemd/system-preset/75-qubes-vm.preset | while read action unit_name; do
    case "$action" in
    (disable)
        if [ -f /lib/systemd/system/$unit_name ]; then
            if ! fgrep -q '[Install]' /lib/systemd/system/$unit_name; then
                # forcibly disable
                ln -sf /dev/null /etc/systemd/system/$unit_name
            fi
        fi
        ;;
    *)
        # preset-all is not available in fc20; so preset each unit file listed in 75-qubes-vm.preset
        if [ $1 -eq 1 -a "${PRESET_FAILED}" -eq 1 ]; then
            systemctl --no-reload preset "${unit_name}" > /dev/null 2>&1 || true
        fi
        ;;
    esac
done

/bin/systemctl daemon-reload

exit 0

%postun systemd

#Do not run this part on upgrades
if [ "$1" != 0 ] ; then
    exit 0
fi

for srv in qubes-dvm qubes-sysinit qubes-misc-post qubes-mount-dirs qubes-netwatcher qubes-network qubes-qrexec-agent; do
    /bin/systemctl disable $srv.service
do
