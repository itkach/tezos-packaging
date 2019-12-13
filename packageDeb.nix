# SPDX-FileCopyrightText: 2019 TQ Tezos <https://tqtezos.com/>
#
# SPDX-License-Identifier: MPL-2.0
{ stdenv, writeTextFile, dpkg }:
pkgDesc:

let
  project = pkgDesc.project;
  version = pkgDesc.version;
  revision = pkgDesc.gitRevision;
  pkgArch = pkgDesc.arch;
  bin = pkgDesc.bin;
  pkgName = "${project}_0ubuntu${version}-${revision}_${pkgArch}";

  writeControlFile = writeTextFile {
    name = "control";
    text = ''
      Package: ${project}
      Version: ${version}-${revision}
      Priority: optional
      Architecture: ${pkgDesc.arch}
      Depends: ${pkgDesc.dependencies}
      Maintainer: ${pkgDesc.maintainer}
      Description: ${project}
       ${pkgDesc.description}
    '';
  };

in stdenv.mkDerivation rec {
  name = "${pkgName}.deb";

  nativeBuildInputs = [ dpkg ];

  phases = "packagePhase";

  packagePhase = ''
    mkdir ${pkgName}
    mkdir -p ${pkgName}/usr/local/bin
    cp ${bin} ${pkgName}/usr/local/bin/${project}

    mkdir ${pkgName}/DEBIAN
    cp ${writeControlFile} ${pkgName}/DEBIAN/control

    dpkg-deb --build ${pkgName}
    mkdir -p $out
    cp ${name} $out/
  '';
}