#!/usr/bin/env python3
"""
Documentation Downloader for RAG-NetTwin
Downloads free vendor documentation PDFs to expand the knowledge base.
"""

import urllib.request
from pathlib import Path
from typing import List, Dict

DOCS_DIR = Path("data/raw_docs")
DOCS_DIR.mkdir(exist_ok=True)

DOCUMENTATION_URLS = {
    # ============================================
    # MODERN/ADVANCED TECH DOCS (For KB gaps)
    # ============================================
    # VXLAN Documentation
    "cisco_vxlan_nexus": {
        "url": "https://www.cisco.com/c/en/us/td/docs/dcn/nx-os/nexus9000/102x/configuration/vxlan/cisco-nexus-9000-series-nx-os-vxlan-configuration-guide-release-102x/m_configuring_vxlan_93x.pdf",
        "filename": "cisco_vxlan_nexus.pdf",
        "vendor": "cisco",
        "os_version": "nxos-9.3",
        "doc_type": "config_guide",
        "title": "Cisco Nexus VXLAN Configuration Guide",
    },
    # DMVPN Documentation
    "cisco_dmvpn": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/sec_conn_dmvpn/configuration/15-mt/sec-conn-dmvpn-15-mt-book.pdf",
        "filename": "cisco_dmvpn.pdf",
        "vendor": "cisco",
        "os_version": "ios-15m",
        "doc_type": "config_guide",
        "title": "Cisco DMVPN Configuration Guide",
    },
    # sFlow Documentation
    "cisco_sflow": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst2960l/software/15-2_7_e/configuration_guide/sys_mgmt/b_1527e_sys_mgmt_2960l_cg/configuring_sflow.pdf",
        "filename": "cisco_sflow.pdf",
        "vendor": "cisco",
        "os_version": "ios-15.2",
        "doc_type": "config_guide",
        "title": "Cisco sFlow Configuration Guide",
    },
    # QoS Configuration (MQC - Modular QoS)
    "cisco_qos_xe17": {
        "url": "https://www.cisco.com/c/en/us/td/docs/routers/ios/config/17-x/qos/b-quality-of-service.pdf",
        "filename": "cisco_qos_xe17.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17",
        "doc_type": "config_guide",
        "title": "Cisco QoS Configuration Guide IOS XE 17.x",
    },
    "cisco_qos_mqc": {
        "url": "https://www.cisco.com/c/en/us/td/docs/routers/ios/config/17-x/qos/b-quality-of-service/m_qos-apply.pdf",
        "filename": "cisco_qos_mqc.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17",
        "doc_type": "config_guide",
        "title": "Cisco MQC QoS Configuration Guide",
    },
    "cisco_qos_ncs540": {
        "url": "https://www.cisco.com/c/en/us/td/docs/iosxr/ncs5xx/qos/24xx/b-qos-cg-24xx-ncs540.pdf",
        "filename": "cisco_qos_ncs540.pdf",
        "vendor": "cisco",
        "os_version": "ios-xr",
        "doc_type": "config_guide",
        "title": "Cisco NCS540 QoS Configuration Guide",
    },
    # CBWFQ Specific
    "cisco_qos_congestion": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/qos_conmgt/configuration/12-4t/qos-conmgt-12-4t-book.pdf",
        "filename": "cisco_qos_congestion.pdf",
        "vendor": "cisco",
        "os_version": "ios-12.4",
        "doc_type": "config_guide",
        "title": "Cisco QoS Congestion Management Guide (CBWFQ)",
    },
    # QoS Congestion Management XE 16
    "cisco_qos_congestion_xe16": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/qos_conmgt/configuration/xe-16-7/qos-conmgt-xe-16-7-book.pdf",
        "filename": "cisco_qos_congestion_xe16.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-16.7",
        "doc_type": "config_guide",
        "title": "Cisco QoS Congestion Management Guide XE 16.7",
    },
    # LLQ Low Latency Queueing
    "cisco_llq": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/qos_conmgt/configuration/xe-17/qos-conmgt-xe-17-book.pdf",
        "filename": "cisco_llq.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17",
        "doc_type": "config_guide",
        "title": "Cisco LLQ Low Latency Queueing Configuration Guide",
    },
    # NETCONF/RESTCONF
    "cisco_netconf": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/17-16/b_17-16_programmability_cg.pdf",
        "filename": "cisco_netconf.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17.16",
        "doc_type": "config_guide",
        "title": "Cisco NETCONF/YANG Configuration Guide",
    },
    # sFlow for different platforms
    "cisco_sflow_nexus9k": {
        "url": "https://www.cisco.com/c/en/us/td/docs/dcn/nx-os/nexus9000/101x/configuration/system-management/cisco-nexus-9000-series-nx-os-system-management-configuration-guide-101x/m-configuring-sflow.pdf",
        "filename": "cisco_sflow_nexus9k.pdf",
        "vendor": "cisco",
        "os_version": "nxos-10.1",
        "doc_type": "config_guide",
        "title": "Cisco Nexus 9000 sFlow Configuration",
    },
    "cisco_sflow_nexus3k": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus3000/sw/system_mgmt/93x/system-management/b-cisco-nexus-3000-series-nx-os-system-management-configuration-guide-93x/b-cisco-nexus-3000-series-nx-os-system-management-configuration-guide-93x_chapter_010100.pdf",
        "filename": "cisco_sflow_nexus3k.pdf",
        "vendor": "cisco",
        "os_version": "nxos-9.3",
        "doc_type": "config_guide",
        "title": "Cisco Nexus 3000 sFlow Configuration",
    },
    # MPLS Configuration
    "cisco_mpls": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/mp_l3vpn/command/mp-l3vpn-cr-book.pdf",
        "filename": "cisco_mpls.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17",
        "doc_type": "config_guide",
        "title": "Cisco MPLS VPN Configuration Guide",
    },
    # ============================================
    # Juniper Documentation (Publicly Available)
    # ============================================
    "junos_cli": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/cli/cli.pdf",
        "filename": "junos_cli.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "cli_user_guide",
        "title": "Juniper JunOS CLI User Guide",
    },
    "junos_bgp": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/bgp/bgp.pdf",
        "filename": "junos_bgp_config.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS BGP Configuration Guide",
    },
    "junos_ospf": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/ospf/ospf.pdf",
        "filename": "junos_ospf.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS OSPF User Guide",
    },
    "junos_static_routing": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/static-routing/static-routing.pdf",
        "filename": "junos_static_routing.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Protocol-Independent Routing Guide",
    },
    "junos_routing_policy": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/routing-policy/routing-policy.pdf",
        "filename": "junos_routing_policy.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Routing Policies and Firewall Filters Guide",
    },
    "junos_routing_overview": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/routing-overview/routing-overview.pdf",
        "filename": "junos_routing_overview.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Routing Protocols Overview",
    },
    "junos_security": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/security-policies/security-policies.pdf",
        "filename": "junos_security.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Security Policies User Guide",
    },
    "junos_openconfig": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/open-config/open-config.pdf",
        "filename": "junos_openconfig.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS OpenConfig User Guide",
    },
    "junos_stp": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/stp-l2/stp-l2.pdf",
        "filename": "junos_stp.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Spanning-Tree Protocols User Guide",
    },
    "junos_ethernet_switching": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/multicast-l2/multicast-l2.pdf",
        "filename": "junos_ethernet_switching.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Ethernet Switching User Guide",
    },
    "junos_dhcp": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/dhcp/dhcp.pdf",
        "filename": "junos_dhcp.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS DHCP User Guide",
    },
    "junos_timing": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/time-mgmt/time-mgmt.pdf",
        "filename": "junos_timing.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Timing and Synchronization Guide",
    },
    "junos_interfaces_switches": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/interfaces-ethernet-switches/interfaces-ethernet-switches.pdf",
        "filename": "junos_interfaces_switches.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Interfaces User Guide for Switches",
    },
    "junos_virtual_chassis": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/virtual-chassis/virtual-chassis.pdf",
        "filename": "junos_virtual_chassis.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Virtual Chassis User Guide",
    },
    "junos_cos": {
        "url": "https://www.juniper.net/documentation/us/en/software/junos/cos-ex/cos-ex.pdf",
        "filename": "junos_cos.pdf",
        "vendor": "juniper",
        "os_version": "junos-24.2",
        "doc_type": "config_guide",
        "title": "Juniper JunOS Class of Service User Guide",
    },
    # Cisco Documentation (Publicly Available)
    "cisco_security_17": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9400/software/release/17-14/configuration_guide/sec/b_1714_sec_9400_cg.pdf",
        "filename": "cisco_security_17_14.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17.14",
        "doc_type": "config_guide",
        "title": "Cisco IOS XE Security Configuration Guide 17.14",
    },
    "cisco_routing_17_15": {
        "url": "https://www.cisco.com/c/en/us/td/docs/switches/lan/catalyst9400/software/release/17-15/configuration_guide/rtng/b_1715_rtng_9400_cg.pdf",
        "filename": "cisco_routing_17_15.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17.15",
        "doc_type": "config_guide",
        "title": "Cisco IOS XE IP Routing Configuration Guide 17.15",
    },
    "cisco_nat": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/ipaddr_nat/configuration/xe-16-9/nat-xe-16-9-book.pdf",
        "filename": "cisco_nat_config.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-16.9",
        "doc_type": "config_guide",
        "title": "Cisco IOS XE NAT Configuration Guide",
    },
    "cisco_programmability_17_16": {
        "url": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/prog/configuration/1716/b_1716_programmability_cg.pdf",
        "filename": "cisco_programmability_17_16.pdf",
        "vendor": "cisco",
        "os_version": "ios-xe-17.16",
        "doc_type": "config_guide",
        "title": "Cisco IOS XE Programmability Configuration Guide 17.16",
    },
}


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file from URL to destination path."""
    try:
        print(f"  Downloading: {url[:60]}...")
        urllib.request.urlretrieve(url, dest_path)
        size = dest_path.stat().st_size / (1024 * 1024)  # MB
        print(f"  ✓ Downloaded: {dest_path.name} ({size:.1f} MB)")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


from typing import Any, Optional  # noqa: E402


def download_documentation(
    download_all: bool = True, specific_keys: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Download documentation PDFs."""
    downloaded = []

    if specific_keys:
        to_download = {
            k: v for k, v in DOCUMENTATION_URLS.items() if k in specific_keys
        }
    elif download_all:
        to_download = DOCUMENTATION_URLS
    else:
        # Only Juniper (to balance the knowledge base)
        to_download = {
            k: v for k, v in DOCUMENTATION_URLS.items() if v["vendor"] == "juniper"
        }

    print(f"\nDownloading {len(to_download)} documentation files...")
    print("=" * 60)

    for key, info in to_download.items():
        dest_path = DOCS_DIR / info["filename"]

        # Skip if already exists
        if dest_path.exists():
            print(f"  ⊘ Skipping (exists): {dest_path.name}")
            downloaded.append(
                {
                    "title": info["title"],
                    "vendor": info["vendor"],
                    "os_version": info["os_version"],
                    "file_path": str(dest_path),
                    "doc_type": info["doc_type"],
                }
            )
            continue

        if download_file(info["url"], dest_path):
            downloaded.append(
                {
                    "title": info["title"],
                    "vendor": info["vendor"],
                    "os_version": info["os_version"],
                    "file_path": str(dest_path),
                    "doc_type": info["doc_type"],
                }
            )

    return downloaded


def update_doc_index(new_docs: List[Dict]):
    """Update doc_index.json with new documents."""
    index_path = Path("data/doc_index.json")

    # Load existing index
    existing = []
    if index_path.exists():
        import json

        with open(index_path, "r") as f:
            existing = json.load(f)

    # Add new documents (avoiding duplicates by filename)
    existing_paths = {Path(d["file_path"]).name for d in existing}

    for doc in new_docs:
        if Path(doc["file_path"]).name not in existing_paths:
            existing.append(doc)
            print(f"  + Added to index: {doc['title']}")
        else:
            print(f"  ⊘ Already in index: {doc['title']}")

    # Save updated index
    with open(index_path, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"\n✓ Updated doc_index.json with {len(new_docs)} documents")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Download vendor documentation for RAG-NetTwin"
    )
    parser.add_argument(
        "--juniper-only",
        action="store_true",
        help="Download only Juniper docs (to balance KB)",
    )
    parser.add_argument(
        "--cisco-only", action="store_true", help="Download only Cisco docs"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available documentation"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be downloaded"
    )
    args = parser.parse_args()

    if args.list:
        print("\nAvailable documentation to download:")
        print("=" * 60)
        for key, info in DOCUMENTATION_URLS.items():
            status = "✓" if (DOCS_DIR / info["filename"]).exists() else "○"
            print(f"  {status} {info['title']} ({info['vendor']})")
        print()
        return

    # Determine what to download
    if args.juniper_only:
        docs = download_documentation(download_all=False)
    elif args.cisco_only:
        docs = download_documentation(
            download_all=True,
            specific_keys=[
                k for k, v in DOCUMENTATION_URLS.items() if v["vendor"] == "cisco"
            ],
        )
    else:
        docs = download_documentation(download_all=True)

    if docs:
        update_doc_index(docs)
        print("\n" + "=" * 60)
        print("Next steps:")
        print("  1. Review downloaded files in data/raw_docs/")
        print("  2. Run: uv run -m data_processing.pipeline")
        print("  3. Or run: uv run run_paper_eval.py")


if __name__ == "__main__":
    main()
