import re
from enum import Enum
from typing import List, Optional
from colorama import Fore, Style
from pydantic import BaseModel, Field, create_model
from rich import print as rprint

from llm_serv.structured_response.from_text import response_from_xml
from llm_serv.structured_response.to_text import response_to_xml


class StructuredResponse(BaseModel):
    class Config:
        validate_assignment=False
        arbitrary_types_allowed=True
    
    @classmethod
    def from_xml(cls, xml: str, exclude_fields: List[str] = []) -> 'StructuredResponse':

        print(f"\n\n\n\nParsing XML: {xml}")
        print(xml)
        print("\n\n\n\n")

        return response_from_xml(xml, return_class=cls, is_root=True, exclude_fields=exclude_fields)
    
    def from_json(self, json: str) -> 'StructuredResponse':
        pass
    
    @classmethod
    def to_xml(cls, exclude_fields: List[str] = []) -> str:
        return response_to_xml(object=cls, exclude_fields=exclude_fields)
    
    @classmethod
    def to_json(self) -> str:
        # return response_to_json(object=self, is_root=True)
        pass

    @classmethod
    def deprecated_to_text(cls, is_root=True) -> str:
        # Create a temporary model with full validation
        TempModel = create_model(
            f"Temp{cls.__name__}",
            __base__=BaseModel,
            **{name: (field.annotation, field) for name, field in cls.model_fields.items()}
        )
        
        instructions = []
        if is_root:
            instructions.append("\nFormatting instructions: respond without any other explanations or comments, prepended or appended to the <response> tags. Pay attention that all fields are attended to, and properly enclosed within opening and closing tag.\n")
        
        # Build example response section
        example_lines = []
        indent = "    " if is_root else "        "
        tag_name = "response" if is_root else cls.__name__.lower()
        
        example_lines.append(f"<{tag_name}>")
        for field_name, field_info in cls.model_fields.items():
            field_type = field_info.annotation
            
            # Check if field is a subclass of ExampleBaseClass
            if isinstance(field_type, type) and issubclass(field_type, StructuredResponse):
                example_lines.append(f"{indent}<{field_name}>")
                sub_example = field_type.to_text(is_root=False)
                sub_lines = sub_example.split('\n')
                # Take all content between the outer tags, including nested content
                content_lines = [line for line in sub_lines if line.strip()]  # Remove empty lines
                start_idx = 1  # Skip first tag
                end_idx = len(content_lines) - 1  # Skip last tag
                sub_example_lines = content_lines[start_idx:end_idx]
                example_lines.extend(f"{indent}    {line}" for line in sub_example_lines)
                example_lines.append(f"{indent}</{field_name}>")
            else:
                example_lines.append(f"{indent}<{field_name}>[Fill {field_name} value here]</{field_name}>")
        
        example_lines.append(f"</{tag_name}>")
        
        if is_root:
            instructions.append("\n".join(example_lines))            
        else:
            return "\n".join(example_lines)
        
        # Collect all field descriptions, starting with nested classes
        all_descriptions = []
        for field_name, field_info in cls.model_fields.items():
            field_type = field_info.annotation
            
            # If field is a subclass of ExampleBaseClass, get its descriptions first
            if isinstance(field_type, type) and issubclass(field_type, StructuredResponse):
                all_descriptions.append(f"\nHere is the description for each field for the <{field_name}> element:")
                sub_model = create_model(
                    f"Temp{field_type.__name__}",
                    __base__=BaseModel,
                    **{name: (f.annotation, f) for name, f in field_type.model_fields.items()}
                )
                for sub_field_name, sub_field_info in sub_model.model_fields.items():
                    all_descriptions.append(field_type._get_field_description(sub_field_name, sub_field_info))
        
        # Add root class descriptions
        all_descriptions.append(f"\nHere is the description for each field for the <response> main element:")
        for field_name, field_info in TempModel.model_fields.items():
            all_descriptions.append(cls._get_field_description(field_name, field_info))
        
        instructions.extend(all_descriptions)
        return "\n".join(instructions)
    
    @staticmethod
    def _get_field_description(field_name: str, field_info) -> str:
        field_type = field_info.annotation
        field_instr = f"\n{field_name}:"
        
        # Check if it's a subclass of ExampleBaseClass
        if isinstance(field_type, type) and issubclass(field_type, StructuredResponse):
            field_instr += f"\n  - Type: a group containing further sub fields"
        else:
            field_instr += f"\n  - Type: {getattr(field_type, '__name__', str(field_type))}"
        
        # Add existing constraint checks here (unchanged)
        for constraint in field_info.metadata:
            # ... (keep existing constraint checks)
            pass
            
        if field_info.description:
            field_instr += f"\n  - Description: {field_info.description}"
            
        if isinstance(field_type, type) and issubclass(field_type, Enum):
            field_instr += f"\n  - Allowed values: {', '.join([e.value for e in field_type])}"
            
        field_instr += f"\n  - It is always enclosed between <{field_name}> open and </{field_name}> closing tags."
        
        return field_instr

    @classmethod
    def deprecated_from_text(cls, text: str) -> 'StructuredResponse':
        text = text.strip()
        # Remove outer response tags if present
        text = re.sub(r'</?response>', '', text)
        
        field_values = {}
        
        for field_name, field_info in cls.model_fields.items():
            field_type = field_info.annotation
            
            # Extract content between tags
            pattern = rf'<{field_name}>(.*?)</{field_name}>'
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            
            if not match:
                raise ValueError(f"Field {field_name} not found in the input text: \n---\n{text}\n---\n")
            
            content = match.group(1).strip()
            
            # Handle nested ExampleBaseClass
            if isinstance(field_type, type) and issubclass(field_type, StructuredResponse):
                # Recursively parse nested content
                field_values[field_name] = field_type.from_text(content)
            # Handle other BaseModel subclasses
            elif isinstance(field_type, type) and issubclass(field_type, BaseModel):
                field_values[field_name] = field_type.model_validate_json(content)
            # Handle Enum types
            elif isinstance(field_type, type) and issubclass(field_type, Enum):
                field_values[field_name] = field_type(content)
            # Handle basic types (str, int, float, etc.)
            else:
                try:
                    field_values[field_name] = field_type(content)
                except ValueError as e:
                    raise ValueError(f"Could not convert value '{content}' to type {field_type} for field {field_name}: {str(e)}")
        
        return cls(**field_values)
