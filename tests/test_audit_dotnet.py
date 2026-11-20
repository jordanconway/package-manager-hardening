# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for audit_dotnet()."""

import audit
import pytest
from conftest import make_workflow, write_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_csproj(tmp_path, name="App.csproj", packages=None):
    """Write a minimal SDK-style .csproj with optional PackageReference entries."""
    refs = ""
    if packages:
        for pkg, ver in packages.items():
            refs += f'    <PackageReference Include="{pkg}" Version="{ver}" />\n'
    content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
{refs}  </ItemGroup>
</Project>
"""
    return write_file(tmp_path, name, content)


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------

def test_lockfile_present_passes(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "packages.lock.json", '{"version": 1, "dependencies": {}}')
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_lockfile_missing_fails(tmp_path):
    make_csproj(tmp_path)
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


def test_lockfile_gitignored(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "packages.lock.json", "{}")
    write_file(tmp_path, ".gitignore", "packages.lock.json\n")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lockfile"]["gitignored"] is True


def test_lockfile_in_subdirectory_detected(tmp_path):
    """packages.lock.json next to a nested .csproj should be found."""
    write_file(tmp_path, "src/MyApp/MyApp.csproj", "<Project />")
    write_file(tmp_path, "src/MyApp/packages.lock.json", '{"version": 1}')
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lockfile"]["status"] == "pass"


def test_lockfile_in_bin_ignored(tmp_path):
    """packages.lock.json inside bin/ or obj/ should not count."""
    make_csproj(tmp_path)
    write_file(tmp_path, "bin/Debug/net8.0/packages.lock.json", "{}")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lockfile"]["status"] == "fail"


# ---------------------------------------------------------------------------
# RestorePackagesWithLockFile opt-in
# ---------------------------------------------------------------------------

def test_lock_opt_in_in_csproj(tmp_path):
    content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
  </PropertyGroup>
</Project>"""
    write_file(tmp_path, "App.csproj", content)
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lock_file_opt_in"]["status"] == "pass"
    assert result["lock_file_opt_in"]["enabled"] is True


def test_lock_opt_in_in_directory_build_props(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "Directory.Build.props", """<Project>
  <PropertyGroup>
    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
  </PropertyGroup>
</Project>""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lock_file_opt_in"]["status"] == "pass"


def test_lock_opt_in_missing_fails(tmp_path):
    make_csproj(tmp_path)
    result = audit.audit_dotnet(str(tmp_path))
    assert result["lock_file_opt_in"]["status"] == "fail"
    assert result["lock_file_opt_in"]["enabled"] is False


# ---------------------------------------------------------------------------
# Exact version pins
# ---------------------------------------------------------------------------

def test_exact_bare_version_passes(tmp_path):
    make_csproj(tmp_path, packages={"Newtonsoft.Json": "13.0.3", "Serilog": "4.2.0"})
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"
    assert result["exact_pins"]["loose_count"] == 0


def test_exact_bracket_version_passes(tmp_path):
    make_csproj(tmp_path, packages={"Newtonsoft.Json": "[13.0.3]"})
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


def test_wildcard_version_flagged(tmp_path):
    make_csproj(tmp_path, packages={"Newtonsoft.Json": "*"})
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose_count"] == 1


def test_floating_prerelease_flagged(tmp_path):
    make_csproj(tmp_path, packages={"Newtonsoft.Json": "*-*"})
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_range_version_flagged(tmp_path):
    make_csproj(tmp_path, packages={"Serilog": "[4.0.0, 5.0.0)"})
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose_count"] == 1


def test_open_ended_range_flagged(tmp_path):
    make_csproj(tmp_path, packages={"Serilog": "[4.0.0,)"})
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"


def test_directory_packages_props_wildcard_flagged(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "Directory.Packages.props", """<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Newtonsoft.Json" Version="*" />
  </ItemGroup>
</Project>""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "fail"
    assert result["exact_pins"]["loose_count"] == 1


def test_directory_packages_props_exact_passes(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "Directory.Packages.props", """<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Newtonsoft.Json" Version="[13.0.3]" />
  </ItemGroup>
</Project>""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["exact_pins"]["status"] == "pass"


# ---------------------------------------------------------------------------
# Central Package Management
# ---------------------------------------------------------------------------

def test_cpm_enabled_passes(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "Directory.Packages.props", """<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
  </PropertyGroup>
</Project>""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["central_package_management"]["status"] == "pass"
    assert result["central_package_management"]["enabled"] is True


def test_cpm_missing_fails(tmp_path):
    make_csproj(tmp_path)
    result = audit.audit_dotnet(str(tmp_path))
    assert result["central_package_management"]["status"] == "fail"
    assert result["central_package_management"]["enabled"] is False


def test_cpm_file_present_but_not_enabled(tmp_path):
    """Directory.Packages.props without ManagePackageVersionsCentrally=true."""
    make_csproj(tmp_path)
    write_file(tmp_path, "Directory.Packages.props", "<Project></Project>")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["central_package_management"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Package Source Mapping
# ---------------------------------------------------------------------------

def test_source_mapping_present_passes(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "nuget.config", """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSourceMapping>
    <packageSource key="nuget.org">
      <package pattern="*" />
    </packageSource>
  </packageSourceMapping>
</configuration>""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["source_mapping"]["status"] == "pass"
    assert result["source_mapping"]["enabled"] is True


def test_source_mapping_missing_fails(tmp_path):
    make_csproj(tmp_path)
    result = audit.audit_dotnet(str(tmp_path))
    assert result["source_mapping"]["status"] == "fail"
    assert result["source_mapping"]["enabled"] is False


def test_nuget_config_without_mapping_fails(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "nuget.config", """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
</configuration>""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["source_mapping"]["status"] == "fail"


# ---------------------------------------------------------------------------
# CI patterns
# ---------------------------------------------------------------------------

AUDIT_GATE_PROPS = """<Project>
  <PropertyGroup>
    <NuGetAuditMode>all</NuGetAuditMode>
    <WarningsAsErrors>$(WarningsAsErrors);NU1901;NU1902;NU1903;NU1904</WarningsAsErrors>
  </PropertyGroup>
</Project>
"""


def test_ci_locked_mode_and_audit_gate_passes(tmp_path):
    make_csproj(tmp_path)
    write_file(tmp_path, "Directory.Build.props", AUDIT_GATE_PROPS)
    make_workflow(tmp_path, "ci.yml", """steps:
  - run: dotnet restore --locked-mode
""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["ci"]["locked_mode"] is True
    assert result["ci"]["vulnerability_gate"] is True
    assert result["ci"]["nuget_audit_mode"] == "all"
    assert result["ci"]["status"] == "pass"


GATE_WITHOUT_MODE = AUDIT_GATE_PROPS.replace("    <NuGetAuditMode>all</NuGetAuditMode>\n", "")
LOCKED_RESTORE = "steps:\n  - run: dotnet restore --locked-mode\n"


def _csproj_targeting(tmp_path, element):
    return write_file(
        tmp_path,
        "App.csproj",
        f'<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    {element}\n  </PropertyGroup>\n</Project>\n',
    )


@pytest.mark.parametrize(
    "element",
    [
        "<TargetFramework>net8.0</TargetFramework>",
        "<TargetFramework>netstandard2.0</TargetFramework>",
        "<TargetFramework>net48</TargetFramework>",
        "<TargetFrameworks>net10.0;net8.0</TargetFrameworks>",
        "<TargetFramework>$(AppFramework)</TargetFramework>",
        "<OutputType>Exe</OutputType>",
    ],
)
def test_ci_gate_without_audit_mode_all_fails_below_net10(tmp_path, element):
    """Below net10.0 NuGetAuditMode defaults to `direct`, so transitives are unaudited."""
    _csproj_targeting(tmp_path, element)
    write_file(tmp_path, "Directory.Build.props", GATE_WITHOUT_MODE)
    make_workflow(tmp_path, "ci.yml", LOCKED_RESTORE)
    ci = audit.audit_dotnet(str(tmp_path))["ci"]
    assert ci["vulnerability_gate"] is True
    assert ci["transitive_audit"] is False
    assert ci["status"] == "fail"
    assert "NuGetAuditMode" in ci["note"]


@pytest.mark.parametrize(
    "element",
    [
        "<TargetFramework>net10.0</TargetFramework>",
        "<TargetFramework>net10.0-windows</TargetFramework>",
        "<TargetFrameworks>net10.0;net11.0</TargetFrameworks>",
    ],
)
def test_ci_gate_without_audit_mode_passes_on_net10_and_later(tmp_path, element):
    _csproj_targeting(tmp_path, element)
    write_file(tmp_path, "Directory.Build.props", GATE_WITHOUT_MODE)
    make_workflow(tmp_path, "ci.yml", LOCKED_RESTORE)
    ci = audit.audit_dotnet(str(tmp_path))["ci"]
    assert ci["transitive_audit"] is True
    assert ci["status"] == "pass"
    assert "note" not in ci


def test_ci_explicit_direct_mode_fails_even_on_net10(tmp_path):
    _csproj_targeting(tmp_path, "<TargetFramework>net10.0</TargetFramework>")
    write_file(
        tmp_path,
        "Directory.Build.props",
        AUDIT_GATE_PROPS.replace("<NuGetAuditMode>all<", "<NuGetAuditMode>direct<"),
    )
    make_workflow(tmp_path, "ci.yml", LOCKED_RESTORE)
    ci = audit.audit_dotnet(str(tmp_path))["ci"]
    assert ci["nuget_audit_mode"] == "direct"
    assert ci["transitive_audit"] is False
    assert ci["status"] == "fail"


def test_ci_vulnerable_listing_alone_is_not_a_gate(tmp_path):
    """`dotnet list package --vulnerable` exits 0 on findings, so it cannot gate CI."""
    make_csproj(tmp_path)
    make_workflow(tmp_path, "ci.yml", """steps:
  - run: dotnet restore --locked-mode
  - run: dotnet list package --vulnerable --include-transitive
""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["ci"]["locked_mode"] is True
    assert result["ci"]["vulnerability_report"] is True
    assert result["ci"]["vulnerability_gate"] is False
    assert result["ci"]["status"] == "fail"


def test_ci_audit_gate_ignored_when_nuget_audit_disabled(tmp_path):
    make_csproj(tmp_path)
    write_file(
        tmp_path,
        "Directory.Build.props",
        AUDIT_GATE_PROPS.replace("<NuGetAuditMode>", "<NuGetAudit>false</NuGetAudit>\n    <NuGetAuditMode>"),
    )
    make_workflow(tmp_path, "ci.yml", "steps:\n  - run: dotnet restore --locked-mode\n")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["ci"]["vulnerability_gate"] is False
    assert result["ci"]["status"] == "fail"


def test_ci_missing_locked_mode_fails(tmp_path):
    make_csproj(tmp_path)
    make_workflow(tmp_path, "ci.yml", """steps:
  - run: dotnet restore
  - run: dotnet list package --vulnerable
""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["ci"]["locked_mode"] is False
    assert result["ci"]["status"] == "fail"


def test_ci_missing_vuln_check_fails(tmp_path):
    make_csproj(tmp_path)
    make_workflow(tmp_path, "ci.yml", """steps:
  - run: dotnet restore --locked-mode
  - run: dotnet build
""")
    result = audit.audit_dotnet(str(tmp_path))
    assert result["ci"]["vulnerability_gate"] is False
    assert result["ci"]["status"] == "fail"


def test_ci_no_workflows(tmp_path):
    make_csproj(tmp_path)
    result = audit.audit_dotnet(str(tmp_path))
    assert result["ci"]["locked_mode"] is False
    assert result["ci"]["vulnerability_gate"] is False
    assert result["ci"]["status"] == "fail"
