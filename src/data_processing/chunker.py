from typing import List, Dict
import re
from dataclasses import dataclass, asdict

@dataclass
class Chunk:
    id: str
    text: str
    tier: int  # 1=Command Syntax, 2=Patterns, 3=Troubleshooting
    vendor: str
    os_version: str
    command_hierarchy: List[str]
    context_tags: List[str]
    source_file: str
    page_range: List[int]

class HierarchicalChunker:
    """
    Chunk documents into three tiers:
    - Tier 1: Command syntax and parameters
    - Tier 2: Configuration examples and patterns
    - Tier 3: Troubleshooting and edge cases
    """
    
    def __init__(self, vendor: str, os_version: str):
        self.vendor = vendor
        self.os_version = os_version
        self.chunk_id_counter = 0
    
    def chunk_document(self, pages: List[Dict]) -> List[Chunk]:
        """Process pages and create hierarchical chunks"""
        chunks = []
        if not pages:
            return chunks
            
        # Combine pages into larger sections
        sections = self.identify_sections(pages)
        
        for section in sections:
            # Determine tier based on content
            tier = self.classify_tier(section['text'])
            
            # Extract command hierarchy
            commands = self.extract_commands(section['text'])
            
            # Extract context tags
            tags = self.extract_context_tags(section['text'])
            
            # Create chunk
            chunk = Chunk(
                id=f"chunk_{self.chunk_id_counter:05d}",
                text=section['text'],
                tier=tier,
                vendor=self.vendor,
                os_version=self.os_version,
                command_hierarchy=commands,
                context_tags=tags,
                source_file=section['source_file'],
                page_range=[section['start_page'], section['end_page']]
            )
            
            chunks.append(chunk)
            self.chunk_id_counter += 1
        
        return chunks
    
    def identify_sections(self, pages: List[Dict], max_pages: int = 5) -> List[Dict]:
        """Group pages into logical sections with a maximum page limit"""
        if not pages:
            return []
            
        sections = []
        current_section = {
            'text': '',
            'start_page': pages[0]['page_num'],
            'end_page': pages[0]['page_num'],
            'source_file': pages[0]['source_file'],
            'section_title': pages[0]['section_title'],
            'page_count': 0
        }
        
        for i, page in enumerate(pages):
            # Check if this is a new section or if we hit the page limit
            is_new = self.is_new_section(page['section_title'], current_section['section_title'])
            limit_reached = current_section['page_count'] >= max_pages
            
            if is_new or limit_reached:
                # Save previous section
                if current_section['text'].strip():
                    sections.append(current_section)
                
                # Start new section
                current_section = {
                    'text': page['text'],
                    'start_page': page['page_num'],
                    'end_page': page['page_num'],
                    'source_file': page['source_file'],
                    'section_title': page['section_title'],
                    'page_count': 1
                }
            else:
                # Continue current section
                current_section['text'] += '\n' + page['text']
                current_section['end_page'] = page['page_num']
                current_section['page_count'] += 1
        
        # Don't forget the last section
        if current_section['text'].strip():
            sections.append(current_section)
        
        return sections
    
    def classify_tier(self, text: str) -> int:
        """Classify chunk into tier based on content"""
        text_lower = text.lower()
        
        # Tier 1 indicators: Command syntax definitions
        tier1_indicators = [
            'syntax:', 'format:', 'command:', 'parameter:',
            'default:', 'mode:', 'usage guidelines'
        ]
        
        # Tier 3 indicators: Troubleshooting
        tier3_indicators = [
            'troubleshooting:', 'problem:', 'issue:', 'error:',
            'debug:', 'verify:', 'check:'
        ]
        
        # Count indicators
        tier1_score = sum(1 for indicator in tier1_indicators if indicator in text_lower)
        tier3_score = sum(1 for indicator in tier3_indicators if indicator in text_lower)
        
        if tier1_score >= 2:
            return 1  # Command Syntax
        elif tier3_score >= 2:
            return 3  # Troubleshooting
        else:
            return 2  # Configuration Patterns (default)
    
    def extract_commands(self, text: str) -> List[str]:
        """Extract command hierarchy from text (Cisco & Juniper)"""
        commands = []
        
        # Look for command patterns
        command_patterns = [
            # Cisco
            r'\b(ip\s+\w+)',
            r'\b(interface\s+\w+)',
            r'\b(router\s+\w+)',
            r'\b(access-list\s+\w+)',
            r'\b(route-map\s+\w+)',
            # Juniper
            r'\b(set\s+protocols\s+\w+)',
            r'\b(set\s+interfaces\s+\w+)',
            r'\b(set\s+routing-options\s+\w+)',
            r'\b(set\s+policy-options\s+\w+)',
            r'\b(set\s+security\s+\w+)'
        ]
        
        for pattern in command_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            commands.extend(matches)
        
        return list(set(commands))  # Remove duplicates
    
    def extract_context_tags(self, text: str) -> List[str]:
        """Extract context tags from text (Cisco & Juniper)"""
        text_lower = text.lower()
        tags = []
        
        # Define tag mappings
        tag_mappings = {
            'layer3': ['ip address', 'routing', 'ospf', 'bgp', 'eigrp', 'routing-options', 'protocols'],
            'layer2': ['switchport', 'vlan', 'trunk', 'access', 'bridge-domains', 'ether-options'],
            'security': ['acl', 'access-list', 'firewall', 'crypto', 'security-zone', 'security-policy'],
            'management': ['snmp', 'ntp', 'logging', 'aaa', 'system services'],
            'interface': ['gigabitethernet', 'fastethernet', 'serial', 'ge-', 'xe-', 'et-'],
            'ipv4': ['ip address', 'ipv4', 'family inet '],
            'ipv6': ['ipv6 address', 'ipv6', 'family inet6 ']
        }
        
        for tag, keywords in tag_mappings.items():
            if any(keyword in text_lower for keyword in keywords):
                tags.append(tag)
        
        return tags
    
    def is_new_section(self, current_title: str, prev_title: str) -> bool:
        """Determine if this is a new section"""
        if current_title == prev_title:
            return False
        
        # Check if titles are substantially different
        current_words = set(current_title.lower().split())
        prev_words = set(prev_title.lower().split())
        
        if not current_words or not prev_words:
            return True
            
        # If less than 50% word overlap, it's a new section
        overlap = len(current_words & prev_words) / max(len(current_words), len(prev_words))
        if overlap < 0.5:
            return True
        
        return False