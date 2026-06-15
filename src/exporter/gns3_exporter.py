import json
import uuid
import os
from src.schemas.intent import StructuredIntent
from src.utils import setup_logger

logger = setup_logger("GNS3Exporter")


class GNS3Exporter:
    """
    Exports a StructuredIntent to a GNS3 project file (.gns3).
    This enables "Topology-as-Code" for the Digital Twin.
    """

    def __init__(self):
        self.project_id = str(uuid.uuid4())

    def export(
        self, intent: StructuredIntent, output_path: str = "results/topology.gns3"
    ) -> str:
        """
        Converts the StructuredIntent into a GNS3 project JSON structure and writes to disk.
        """
        intent_text = intent.original_text or "Unknown Intent"
        logger.info(
            f"Exporting Digital Twin topology for intent: {intent_text[:50]}..."
        )

        # 1. Initialize Project Skeleton
        project = {
            "name": f"Twin_{int(uuid.uuid1().time)}",
            "project_id": self.project_id,
            "revision": 9,
            "scene_height": 1000,
            "scene_width": 2000,
            "topology": {
                "compute_id": "local",
                "drawings": [],
                "links": [],
                "nodes": [],
            },
        }

        # 2. Add Nodes
        node_map = {}  # device_name -> node_data
        for i, device in enumerate(intent.devices):
            node_id = str(uuid.uuid4())

            # Map vendor to template type
            vendor = (device.vendor or "cisco").lower()
            if vendor == "cisco":
                node_type = "iou"  # Or qemu/dynamips depending on image, but iou/qemu is common for Twin
                symbol = ":/symbols/router.svg"
            elif vendor == "juniper":
                node_type = "qemu"
                symbol = ":/symbols/router.svg"
            else:
                node_type = "vpcs"
                symbol = ":/symbols/vpcs_guest.svg"

            node = {
                "compute_id": "local",
                "name": device.name,
                "node_id": node_id,
                "node_type": node_type,
                "symbol": symbol,
                "x": i * 150
                - (len(intent.devices) * 75),  # Center the topology horizontally
                "y": 0,
                "properties": {
                    "hostname": device.name,
                },
            }
            project["topology"]["nodes"].append(node)
            node_map[device.name] = node

        # 3. Create Links (Linear Topology)
        device_names = list(node_map.keys())
        for i in range(len(device_names) - 1):
            node_a = node_map[device_names[i]]
            node_b = node_map[device_names[i + 1]]

            link = {
                "link_id": str(uuid.uuid4()),
                "nodes": [
                    {
                        "adapter_number": 0,
                        "label": {
                            "rotation": 0,
                            "style": "font-family: 'Arial'; font-size: 10; font-weight: bold",
                            "text": f"Eth{i + 1}",
                            "x": 0,
                            "y": 0,
                        },
                        "node_id": node_a["node_id"],
                        "port_number": i + 1,
                    },
                    {
                        "adapter_number": 0,
                        "label": {
                            "rotation": 0,
                            "style": "font-family: 'Arial'; font-size: 10; font-weight: bold",
                            "text": f"Eth{i}",
                            "x": 0,
                            "y": 0,
                        },
                        "node_id": node_b["node_id"],
                        "port_number": i,
                    },
                ],
            }
            project["topology"]["links"].append(link)

        # 4. Save to Disk
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(project, f, indent=4)

        logger.info(f"Topology successfully exported to {output_path}")
        return output_path


if __name__ == "__main__":
    from src.parser.intent_parser import IntentParser

    parser = IntentParser()
    intent = parser.parse("Configure OSPF between R1 and R2")
    exporter = GNS3Exporter()
    exporter.export(intent)
