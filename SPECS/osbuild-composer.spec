# Do not build with tests by default
# Pass --with tests to rpmbuild to override
%bcond_with tests

# When --with relax_requires is specified osbuild-composer-tests
# will require osbuild-composer only by name, excluding version/release
# This is used internally during nightly pipeline testing!
%bcond_with relax_requires

%global goipath         github.com/osbuild/osbuild-composer

Version:              75

%gometa

%global common_description %{expand:
A service for building customized OS artifacts, such as VM images and OSTree
commits, that uses osbuild under the hood. Besides building images for local
usage, it can also upload images directly to cloud.

It is compatible with composer-cli and cockpit-composer clients.
}

Name:                 osbuild-composer
Release:              1%{?dist}.openela.0.2
Summary:              An image building service based on osbuild

# osbuild-composer doesn't have support for building i686 and armv7hl images
ExcludeArch:          i686 armv7hl

# Upstream license specification: Apache-2.0
License:              Apache-2.0
URL:                  %{gourl}
Source0:              %{gosource}

Patch1:               0001-Add-OpenELA-8-and-9-Support.patch


BuildRequires:        %{?go_compiler:compiler(go-compiler)}%{!?go_compiler:golang}
BuildRequires:        systemd
BuildRequires:        krb5-devel
BuildRequires:        python3-docutils
BuildRequires:        make
# Build requirements of 'theproglottis/gpgme' package
BuildRequires:        gpgme-devel
BuildRequires:        libassuan-devel
%if 0%{?fedora}
BuildRequires:        systemd-rpm-macros
BuildRequires:        git
# DO NOT REMOVE the BUNDLE_START and BUNDLE_END markers as they are used by 'tools/rpm_spec_add_provides_bundle.sh' to generate the Provides: bundled list
# BUNDLE_START
# BUNDLE_END
%endif

Requires:             %{name}-core = %{version}-%{release}
Requires:             %{name}-worker = %{version}-%{release}
Requires:             systemd

Provides:             weldr

%description
%{common_description}

%prep
%if 0%{?rhel}
%forgeautosetup -p1
%else
%goprep -k
%endif

%build
export GOFLAGS="-buildmode=pie"
%if 0%{?rhel}
GO_BUILD_PATH=$PWD/_build
install -m 0755 -vd $(dirname $GO_BUILD_PATH/src/%{goipath})
ln -fs $PWD $GO_BUILD_PATH/src/%{goipath}
cd $GO_BUILD_PATH/src/%{goipath}
install -m 0755 -vd _bin
export PATH=$PWD/_bin${PATH:+:$PATH}
export GOPATH=$GO_BUILD_PATH:%{gopath}
export GOFLAGS+=" -mod=vendor"
%endif

# Set the commit hash so that composer can report what source version
# was used to build it. This has to be set explicitly when calling rpmbuild,
# this script will not attempt to automatically discover it.
%if %{?commit:1}0
export LDFLAGS="${LDFLAGS} -X 'github.com/osbuild/osbuild-composer/internal/common.GitRev=%{commit}'"
%endif
export LDFLAGS="${LDFLAGS} -X 'github.com/osbuild/osbuild-composer/internal/common.RpmVersion=%{name}-%{?epoch:%epoch:}%{version}-%{release}.%{_arch}'"

%gobuild -o _bin/osbuild-composer %{goipath}/cmd/osbuild-composer
%gobuild -o _bin/osbuild-worker %{goipath}/cmd/osbuild-worker

make man

%if %{with tests} || 0%{?rhel}

# Build test binaries with `go test -c`, so that they can take advantage of
# golang's testing package. The golang rpm macros don't support building them
# directly. Thus, do it manually, taking care to also include a build id.
#
# On Fedora, also turn off go modules and set the path to the one into which
# the golang-* packages install source code.
%if 0%{?fedora}
export GO111MODULE=off
export GOPATH=%{gobuilddir}:%{gopath}
%endif

TEST_LDFLAGS="${LDFLAGS:-} -B 0x$(od -N 20 -An -tx1 -w100 /dev/urandom | tr -d ' ')"

go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-composer-cli-tests %{goipath}/cmd/osbuild-composer-cli-tests
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-dnf-json-tests %{goipath}/cmd/osbuild-dnf-json-tests
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-weldr-tests %{goipath}/internal/client/
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-image-tests %{goipath}/cmd/osbuild-image-tests
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-auth-tests %{goipath}/cmd/osbuild-auth-tests
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-koji-tests %{goipath}/cmd/osbuild-koji-tests
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-composer-dbjobqueue-tests %{goipath}/cmd/osbuild-composer-dbjobqueue-tests
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-composer-manifest-tests %{goipath}/cmd/osbuild-composer-manifest-tests
go test -c -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-service-maintenance-tests %{goipath}/cmd/osbuild-service-maintenance
go build -tags=integration -ldflags="${TEST_LDFLAGS}" -o _bin/osbuild-mock-openid-provider %{goipath}/cmd/osbuild-mock-openid-provider

%endif

%install
install -m 0755 -vd                                                %{buildroot}%{_libexecdir}/osbuild-composer
install -m 0755 -vp _bin/osbuild-composer                          %{buildroot}%{_libexecdir}/osbuild-composer/
install -m 0755 -vp _bin/osbuild-worker                            %{buildroot}%{_libexecdir}/osbuild-composer/
install -m 0755 -vp dnf-json                                       %{buildroot}%{_libexecdir}/osbuild-composer/

# Only include repositories for the distribution and release
install -m 0755 -vd                                                %{buildroot}%{_datadir}/osbuild-composer/repositories
# CentOS also defines rhel so we check for centos first
%if 0%{?centos}

# CentOS 9 supports building for CentOS 8 and later
%if 0%{?centos} >= 9
install -m 0644 -vp repositories/centos-*                          %{buildroot}%{_datadir}/osbuild-composer/repositories/
%else
# CentOS 8 only supports building for CentOS 8
install -m 0644 -vp repositories/centos-%{centos}*                 %{buildroot}%{_datadir}/osbuild-composer/repositories/
install -m 0644 -vp repositories/centos-stream-%{centos}*          %{buildroot}%{_datadir}/osbuild-composer/repositories/

%endif
%else
%if 0%{?rhel}
# RHEL 9 supports building for RHEL 8 and later
%if 0%{?rhel} >= 9
install -m 0644 -vp repositories/rhel-*                            %{buildroot}%{_datadir}/osbuild-composer/repositories/

%else
# RHEL 8 only supports building for 8
install -m 0644 -vp repositories/rhel-%{rhel}*                     %{buildroot}%{_datadir}/osbuild-composer/repositories/

%endif
%endif
%endif

%if 0%{?openela}
%if 0%{?openela} >= 9
install -m 0644 -vp repositories/openela-*                           %{buildroot}%{_datadir}/osbuild-composer/repositories/
%else
install -m 0644 -vp repositories/openela-8*                          %{buildroot}%{_datadir}/osbuild-composer/repositories/
%endif
%endif

# Fedora can build for all included fedora releases
%if 0%{?fedora}
install -m 0644 -vp repositories/fedora-*                          %{buildroot}%{_datadir}/osbuild-composer/repositories/
%endif

install -m 0755 -vd                                                %{buildroot}%{_unitdir}
install -m 0644 -vp distribution/*.{service,socket}                %{buildroot}%{_unitdir}/

install -m 0755 -vd                                                %{buildroot}%{_sysusersdir}
install -m 0644 -vp distribution/osbuild-composer.conf             %{buildroot}%{_sysusersdir}/

install -m 0755 -vd                                                %{buildroot}%{_localstatedir}/cache/osbuild-composer/dnf-cache

install -m 0755 -vd                                                %{buildroot}%{_mandir}/man7
install -m 0644 -vp docs/*.7                                       %{buildroot}%{_mandir}/man7/

%if %{with tests} || 0%{?rhel}

install -m 0755 -vd                                                %{buildroot}%{_libexecdir}/osbuild-composer-test
install -m 0755 -vp _bin/osbuild-composer-cli-tests                %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-weldr-tests                       %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-dnf-json-tests                    %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-image-tests                       %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-auth-tests                        %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-koji-tests                        %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-composer-dbjobqueue-tests         %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-composer-manifest-tests           %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-service-maintenance-tests         %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp _bin/osbuild-mock-openid-provider              %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/define-compose-url.sh                    %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/provision.sh                             %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/gen-certs.sh                             %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/gen-ssh.sh                               %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/image-info                               %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/run-koji-container.sh                    %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/koji-compose.py                          %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/libvirt_test.sh                          %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/s3_test.sh                               %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/generic_s3_test.sh                       %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/generic_s3_https_test.sh                 %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/run-mock-auth-servers.sh                 %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/set-env-variables.sh                     %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vp tools/test-case-generators/generate-test-cases %{buildroot}%{_libexecdir}/osbuild-composer-test/
install -m 0755 -vd                                                %{buildroot}%{_libexecdir}/tests/osbuild-composer
install -m 0755 -vp test/cases/*.sh                                %{buildroot}%{_libexecdir}/tests/osbuild-composer/

install -m 0755 -vd                                                %{buildroot}%{_libexecdir}/tests/osbuild-composer/api
install -m 0755 -vp test/cases/api/*.sh                            %{buildroot}%{_libexecdir}/tests/osbuild-composer/api/

install -m 0755 -vd                                                %{buildroot}%{_libexecdir}/tests/osbuild-composer/api/common
install -m 0755 -vp test/cases/api/common/*.sh                     %{buildroot}%{_libexecdir}/tests/osbuild-composer/api/common/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/ansible
install -m 0644 -vp test/data/ansible/*                            %{buildroot}%{_datadir}/tests/osbuild-composer/ansible/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/azure
install -m 0644 -vp test/data/azure/*                              %{buildroot}%{_datadir}/tests/osbuild-composer/azure/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/manifests
install -m 0644 -vp test/data/manifests/*                          %{buildroot}%{_datadir}/tests/osbuild-composer/manifests/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/cloud-init
install -m 0644 -vp test/data/cloud-init/*                         %{buildroot}%{_datadir}/tests/osbuild-composer/cloud-init/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/composer
install -m 0644 -vp test/data/composer/*                           %{buildroot}%{_datadir}/tests/osbuild-composer/composer/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/worker
install -m 0644 -vp test/data/worker/*                             %{buildroot}%{_datadir}/tests/osbuild-composer/worker/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/repositories
install -m 0644 -vp test/data/repositories/*                       %{buildroot}%{_datadir}/tests/osbuild-composer/repositories/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/kerberos
install -m 0644 -vp test/data/kerberos/*                           %{buildroot}%{_datadir}/tests/osbuild-composer/kerberos/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/keyring
install -m 0644 -vp test/data/keyring/id_rsa.pub                   %{buildroot}%{_datadir}/tests/osbuild-composer/keyring/
install -m 0600 -vp test/data/keyring/id_rsa                       %{buildroot}%{_datadir}/tests/osbuild-composer/keyring/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/koji
install -m 0644 -vp test/data/koji/*                               %{buildroot}%{_datadir}/tests/osbuild-composer/koji/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/x509
install -m 0644 -vp test/data/x509/*                               %{buildroot}%{_datadir}/tests/osbuild-composer/x509/

install -m 0755 -vd                                                %{buildroot}%{_datadir}/tests/osbuild-composer/schemas
install -m 0644 -vp pkg/jobqueue/dbjobqueue/schemas/*              %{buildroot}%{_datadir}/tests/osbuild-composer/schemas/

install -m 0755 -vd                                               %{buildroot}%{_datadir}/tests/osbuild-composer/upgrade8to9
install -m 0644 -vp test/data/upgrade8to9/*                       %{buildroot}%{_datadir}/tests/osbuild-composer/upgrade8to9/

%endif

%check
export GOFLAGS="-buildmode=pie"
%if 0%{?rhel}
export GOFLAGS+=" -mod=vendor"
export GOPATH=$PWD/_build:%{gopath}
# cd inside GOPATH, otherwise go with GO111MODULE=off ignores vendor directory
cd $PWD/_build/src/%{goipath}
%gotest ./...
%else
%gocheck
%endif

%post
%systemd_post osbuild-composer.service osbuild-composer.socket osbuild-composer-api.socket osbuild-remote-worker.socket

%preun
%systemd_preun osbuild-composer.service osbuild-composer.socket osbuild-composer-api.socket osbuild-remote-worker.socket

%postun
%systemd_postun_with_restart osbuild-composer.service osbuild-composer.socket osbuild-composer-api.socket osbuild-remote-worker.socket

%files
%license LICENSE
%doc README.md
%{_mandir}/man7/%{name}.7*
%{_unitdir}/osbuild-composer.service
%{_unitdir}/osbuild-composer.socket
%{_unitdir}/osbuild-composer-api.socket
%{_unitdir}/osbuild-local-worker.socket
%{_unitdir}/osbuild-remote-worker.socket
%{_sysusersdir}/osbuild-composer.conf

%package core
Summary:              The core osbuild-composer binary
Requires:             %{name}-dnf-json = %{version}-%{release}

%description core
The core osbuild-composer binary. This is suitable both for spawning in containers and by systemd.

%files core
%{_libexecdir}/osbuild-composer/osbuild-composer
%{_datadir}/osbuild-composer/

%package worker
Summary:              The worker for osbuild-composer
Requires:             systemd
Requires:             qemu-img
Requires:             osbuild >= 80
Requires:             osbuild-ostree >= 80
Requires:             osbuild-lvm2 >= 80
Requires:             osbuild-luks2 >= 80
Requires:             %{name}-dnf-json = %{version}-%{release}

%description worker
The worker for osbuild-composer

%files worker
%{_libexecdir}/osbuild-composer/osbuild-worker
%{_unitdir}/osbuild-worker@.service
%{_unitdir}/osbuild-remote-worker@.service

%post worker
%systemd_post osbuild-worker@.service osbuild-remote-worker@.service

%preun worker
# systemd_preun uses systemctl disable --now which doesn't work well with template services.
# See https://github.com/systemd/systemd/issues/15620
# The following lines mimicks its behaviour by running two commands.
# The scriptlet is supposed to run only when the package is being removed.
if [ $1 -eq 0 ] && [ -d /run/systemd/system ]; then
    # disable and stop all the worker services
    systemctl --no-reload disable osbuild-worker@.service osbuild-remote-worker@.service
    systemctl stop "osbuild-worker@*.service" "osbuild-remote-worker@*.service"
fi

%postun worker
# restart all the worker services
%systemd_postun_with_restart "osbuild-worker@*.service" "osbuild-remote-worker@*.service"

%package dnf-json
Summary:              The dnf-json binary used by osbuild-composer and the workers

# Conflicts with older versions of composer that provide the same files
# this can be removed when RHEL 8 reaches EOL
Conflicts:            osbuild-composer <= 35

%description dnf-json
The dnf-json binary used by osbuild-composer and the workers.

%files dnf-json
%{_libexecdir}/osbuild-composer/dnf-json

%post dnf-json
# Fix ownership of the rpmmd cache files from previous versions where it was owned by root:root
if [ -e /var/cache/osbuild-composer/rpmmd ]; then
    chown -f -R --from root:root _osbuild-composer:_osbuild-composer /var/cache/osbuild-composer/rpmmd
fi

%if %{with tests} || 0%{?rhel}

%package tests
Summary:              Integration tests
%if %{with relax_requires}
Requires:             %{name}
%else
Requires:             %{name} = %{version}-%{release}
%endif
Requires:             composer-cli
Requires:             createrepo_c
Requires:             xorriso
Requires:             qemu-kvm-core
Requires:             systemd-container
Requires:             jq
Requires:             unzip
Requires:             container-selinux
Requires:             dnsmasq
Requires:             krb5-workstation
Requires:             podman
Requires:             python3
Requires:             sssd-krb5
Requires:             libvirt-client libvirt-daemon
Requires:             libvirt-daemon-config-network
Requires:             libvirt-daemon-config-nwfilter
Requires:             libvirt-daemon-driver-interface
Requires:             libvirt-daemon-driver-network
Requires:             libvirt-daemon-driver-nodedev
Requires:             libvirt-daemon-driver-nwfilter
Requires:             libvirt-daemon-driver-qemu
Requires:             libvirt-daemon-driver-secret
Requires:             libvirt-daemon-driver-storage
Requires:             libvirt-daemon-driver-storage-disk
Requires:             libvirt-daemon-kvm
Requires:             qemu-img
Requires:             qemu-kvm
Requires:             rpmdevtools
Requires:             virt-install
Requires:             expect
Requires:             python3-lxml
Requires:             httpd
Requires:             mod_ssl
Requires:             openssl
Requires:             firewalld
Requires:             podman-plugins
Requires:             dnf-plugins-core
Requires:             skopeo
Requires:             make
Requires:             python3-pip
%if 0%{?fedora}
# koji and ansible are not in RHEL repositories. Depending on them breaks RHEL
# gating (see OSCI-1541). The test script must enable EPEL and install those
# packages manually.
Requires:             koji
Requires:             ansible
%endif
%ifarch %{arm}
Requires:             edk2-aarch64
%endif

%description tests
Integration tests to be run on a pristine-dedicated system to test the osbuild-composer package.

%files tests
%{_libexecdir}/osbuild-composer-test/
%{_libexecdir}/tests/osbuild-composer/
%{_datadir}/tests/osbuild-composer/

%endif

%changelog
* Wed Nov 15 2023 Release Engineering <releng@openela.org> - 75.openela.0.2
- Add OpenELA 8 support and host detection
- Add OpenELA 9 support and host detection

* Wed Feb 22 2023 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 75-1
- New upstream release

* Wed Feb 08 2023 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 74-1
- New upstream release

* Wed Jan 25 2023 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 73-1
- New upstream release

* Wed Jan 11 2023 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 72-1
- New upstream release

* Wed Dec 28 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 71-1
- New upstream release

* Wed Dec 14 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 70-1
- New upstream release

* Wed Nov 30 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 69-1
- New upstream release

* Wed Nov 16 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 68-1
- New upstream release

* Wed Nov 02 2022 imagebuilder-bots+imagebuilder-bot@redhat.com <imagebuilder-bot> - 67-1
- New upstream release

* Mon Aug 29 2022 Ondřej Budai <ondrej@budai.cz> - 62-1
- New upstream release

* Wed Aug 24 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 60-1
- New upstream release

* Thu Aug 11 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 59-1
- New upstream release

* Thu Jul 28 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 58-1
- New upstream release

* Mon Jul 18 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 57-1
- New upstream release

* Wed Jun 15 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 55-1
- New upstream release

* Wed Jun 01 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 54-1
- New upstream release

* Mon May 23 2022 imagebuilder-bot <imagebuilder-bots+imagebuilder-bot@redhat.com> - 53-1
- New upstream release

* Wed May 04 2022 Ondřej Budai <ondrej@budai.cz> - 51-1
- New upstream release

* Tue Mar 01 2022 Ondřej Budai <ondrej@budai.cz> - 46-1
- New upstream release

* Sat Feb 19 2022 Ondřej Budai <ondrej@budai.cz> - 45-1
- New upstream release

* Mon Feb 14 2022 Thomas Lavocat <tlavocat@redhat.com> - 44-1
- New upstream release

* Mon Feb 07 2022 Thomas Lavocat <tlavocat@redhat.com> - 43-1
- New upstream release

* Tue Jan 18 2022 Thomas Lavocat <tlavocat@redhat.com> - 42-1
- New upstream release

* Thu Dec 09 2021 Ondřej Budai <ondrej@budai.cz> - 40-1
- New upstream release

* Fri Oct 15 2021 Achilleas Koutsou <achilleas@redhat.com> - 37-1
- New upstream release

* Fri Oct 15 2021 Achilleas Koutsou <achilleas@redhat.com> - 36-1
- New upstream release

* Mon Aug 30 2021 Tom Gundersen <teg@jklm.no> - 33-1
- New upstream release

* Sun Aug 29 2021 Tom Gundersen <teg@jklm.no> - 32-2
- New upstream release

* Thu Aug 12 2021 Ondřej Budai <ondrej@budai.cz> - 31-1
- New upstream release

* Sat Feb 20 2021 Martin Sehnoutka <msehnout@redhat.com> - 28-1
- New upstream release

* Fri Feb 05 2021 Ondrej Budai <obudai@redhat.com> - 27-1
- New upstream release

* Thu Dec 17 2020 Ondrej Budai <obudai@redhat.com> - 26-1
- New upstream release

* Mon Nov 30 2020 Ondrej Budai <obudai@redhat.com> - 25-1
- New upstream release 25 (rhbz#1883481)

* Thu Sep 03 2020 Tom Gundersen <tgunders@redhat.com> - 20.1-1
- New upstream release 20.1 (rhbz#1872370)

* Sun Aug 23 2020 Tom Gundersen <tgunders@redhat.com> - 20-1
- New upstream release 20 (rhbz#1871184 and rhbz#1871179)

* Thu Aug 13 2020 Tom Gundersen <tgunders@redhat.com> - 19-1
- New upstream release 19 (rhbz#1866015 and rhbz#1866013)

* Thu Jul 09 2020 Ondrej Budai <obudai@redhat.com> - 17-1
- New upstream release 17 (rhbz#1831653)
- Obsolete lorax-composer in favor of osbuild-composer (rhbz#1836844)

* Mon Jun 29 2020 Ondrej Budai <obudai@redhat.com> - 16-1
- New upstream release 16 (rhbz#1831653)

* Fri Jun 12 2020 Ondrej Budai <obudai@redhat.com> - 15-1
- New upstream release 15 (rhbz#1831653)

* Thu Jun 04 2020 Ondrej Budai <obudai@redhat.com> - 14-1
- New upstream release 14 (rhbz#1831653)

* Thu May 28 2020 Ondrej Budai <obudai@redhat.com> - 13-1
- New upstream release 13 (rhbz#1831653)

* Tue May 05 2020 Ondrej Budai <obudai@redhat.com> - 11-1
- Initial package (renamed from golang-github-osbuild-composer) (rhbz#1771887)
