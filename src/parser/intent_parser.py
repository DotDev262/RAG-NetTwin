import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

class DeviceIntent(BaseModel):
    name: str = Field(description="Name of the device, e.g., Router-A")
    vendor: str = Field(description="Device vendor, e.g., cisco, juniper", default="cisco")
    os_type: str = Field(description="Operating system type, e.g., ios-xe, junos", default="ios-xe")
    os_version: str = Field(description="OS version, e.g., 17.6", default="17.6")

class StructuredIntent(BaseModel):
    intent_id: Optional[str] = Field(description="Unique identifier for the intent")
    protocol: Optional[str] = Field(description="Network protocol involved, e.g., OSPF, BGP, Static, ACL")
    action: str = Field(description="Action to perform, e.g., create, delete, update, show")
    devices: List[DeviceIntent] = Field(description="List of devices involved in the intent")
    parameters: Dict[str, Any] = Field(description="Key-value pairs of parameters, e.g., {'area': '0', 'ip': '192.168.1.1'}")
    requirements: List[str] = Field(description="Specific requirements or goals, e.g., ['establish_adjacency']")

class IntentParser:
    """Parses natural language intents into structured JSON using LLM."""
    
    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "your_api_key_here":
            raise ValueError("GROQ_API_KEY not found in environment. Please set it in .env")
            
        self.llm = ChatGroq(
            model=model_name,
            temperature=0,
            api_key=api_key
        )
        self.structured_llm = self.llm.with_structured_output(StructuredIntent)
        
    def parse(self, text: str) -> StructuredIntent:
        """Translates NL text to StructuredIntent object."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a network automation expert. Translate the following natural language intent into a structured JSON format for Intent-Based Networking."),
            ("human", "{input}")
        ])
        
        chain = prompt | self.structured_llm
        return chain.invoke({"input": text})

if __name__ == "__main__":
    # Quick test
    try:
        parser = IntentParser()
        test_text = "Configure OSPF area 0 on Router-A (Cisco IOS-XE 17.6) for interface Gig0/1 with IP 192.168.1.1/24"
        result = parser.parse(test_text)
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")
