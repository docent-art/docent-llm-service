from llm_serv.exceptions import StructuredResponseException
from typing import Type, get_origin, get_args, Union, List, Optional, Any, Dict
from enum import Enum
from pydantic import BaseModel
from datetime import date as date_type, datetime as datetime_type, time as time_type
import dateparser
import re
from rich import print as rprint

def extract_children_xml(xml: str) -> Dict[str, str]:
    """
    This method receives a string and returns all top-level children elements as a list of dictionaries.
    An element is a dictionary with the following keys:
    {
        "tag_name": str,
        "type": str,
        "content": str        
    }    
    """
    # Initialize children to store results
    children = []
    
    # Remove whitespace and newlines from ends while preserving internal formatting
    xml = xml.strip()
    
    # Pattern to match XML tags with optional type attribute (single or double quotes) and content
    pattern = r'<(\w+)(?:\s+type=(["\'])(.*?)\2)?\s*>(.*?)</\1>'
    matches = re.finditer(pattern, xml, re.DOTALL)
    
    # Convert matches to list first to check length
    matches_list = list(matches)
    
    for match in matches_list:
        child = {
            "tag_name": match.group(1),
            "type": match.group(3) or "n/a",  # Group 3 is now the type value
            "content": match.group(4)         # Group 4 is now the content
        }
        children.append(child)
        
    return children

def get_field_type(class_type: Type):
    """
    This method reads a class type and returns a list of field types:
    [{
        "field_name": field_name,
        "field_type": field_type,
        "is_optional": is_optional,
        "base_type": base_field_type,
        "list_item_type": list_item_type
    }]    

    Example:
    [{
        'field_name': 'example_time',
        'field_type': <class 'datetime.time'>,
        'is_optional': False,
        'base_type': <class 'datetime.time'>,
        'list_item_type': None
    },
    {
        'field_name': 'example_optional_list_of_subclasstype1',
        'field_type': typing.Optional[typing.List[__main__.SubClassType1]],
        'is_optional': True,
        'base_type': <class 'list'>,
        'list_item_type': <class '__main__.SubClassType1'>
    }]
    """
    fields = []

    for field_name, field_type in class_type.__annotations__.items():  
        # Check if field is Optional (either directly or as Optional[List[...]])
        is_optional = (
            get_origin(field_type) is Union and type(None) in get_args(field_type)
        )
        
        # Get the base type, handling both Optional[Type] and Optional[List[Type]] cases
        if is_optional:
            base_type = next(arg for arg in get_args(field_type) if arg != type(None))
        else:
            base_type = field_type

        # Handle List types (both optional and required)
        list_item_type = None
        if get_origin(base_type) is list:
            list_item_type = get_args(base_type)[0]
            base_type = list  # Set base_type to list for both regular and optional lists
        
        fields.append({
            "field_name": field_name,
            "field_type": field_type,
            "is_optional": is_optional,
            "base_type": base_type,
            "list_item_type": list_item_type
        })
    return fields


def response_from_xml(xml: str, return_class: Type['StructuredResponse'], is_root: bool = True, exclude_fields: List[str] = []) -> 'StructuredResponse':
    try:
        print(f"\nParsing XML for class {return_class.__name__}")
        
        # Clean input from code block markers if present
        if "```xml" in xml:
            xml = xml.split("```xml", 1)[1]
            xml = xml.split("```", 1)[0]
        
        print(f"XML content:\n{xml}")
        
        # Remove XML comments
        xml = re.sub(r'<!--.*?-->', '', xml, flags=re.DOTALL)
        
        # Handle root element
        if is_root:
            xml = xml.replace('<structured_response>', '').replace('</structured_response>', '')
        
        # Extract children elements
        children:dict = extract_children_xml(xml)    
        
        # For each child, determine is there is a corresponding field name in the return_class fields
        # If so, change the child value for "type" with the corresponding field type
        # For example, if the name matches a subclass, change the "type" to the subclass
        field_values = {}
        for field in get_field_type(return_class):  
            field_name = field["field_name"]
            field_type = field["field_type"]
            is_optional = field["is_optional"]
            base_type = field["base_type"]
            list_item_type = field["list_item_type"]
            
            if field_name in exclude_fields:
                continue

            # Skip if field not in children
            child = None
            for elem in children:
                if elem["tag_name"] == field_name:
                    child = elem
            if child is None:
                # Check if field is optional
                if is_optional:
                    field_values[field_name] = None
                    continue
                else:
                    raise Exception(f"Required field {field_name} not found in the following children: {[child['tag_name'] for child in children]}!")
                            
            # Get the raw content
            tag_type = child["type"]        
            content = child["content"]
                    
            # Handle basic types
            if base_type in (str, int, float):
                field_values[field_name] = None
                try:
                    field_values[field_name] = base_type(content)
                except Exception as e:
                    pass
                    #print(f"Warning parsing {field_name} with type {base_type}: {e}, default to None")
                
            # Handle enum types
            elif issubclass(base_type, Enum):
                try:
                    # First try direct value lookup
                    field_values[field_name] = base_type(content)
                except ValueError:                
                    field_values[field_name] = None
                
            # Handle date types
            elif base_type == date_type:
                parsed = dateparser.parse(content)
                field_values[field_name] = parsed.date() if parsed else None
                
            # Handle time types    
            elif base_type == time_type:
                parsed = dateparser.parse(content)
                field_values[field_name] = parsed.time() if parsed else None
                
            # Handle datetime types
            elif base_type == datetime_type:
                field_values[field_name] = dateparser.parse(content)
                
            # Handle classes from BaseModel/StructuredResponse
            elif isinstance(base_type, type) and issubclass(base_type, BaseModel):
                class_pattern = rf'<{base_type.__name__.lower()}>(.*?)</{base_type.__name__.lower()}>'
                class_match = re.search(class_pattern, content, re.DOTALL)
                if class_match:
                    field_values[field_name] = response_from_xml(class_match.group(1), base_type, False)
                else:
                    field_values[field_name] = response_from_xml(content, base_type, False)
                continue

            # Handle lists and optional lists
            elif base_type == list:
                if not content:
                    # Check if the list is optional
                    is_optional = get_origin(field_type) is Union and type(None) in get_args(field_type)
                    field_values[field_name] = None if is_optional else []
                else:
                    items = []
                    # Find all list elements
                    element_pattern = rf'<{field_name}_element.*?>(.*?)</{field_name}_element>'
                    element_matches = re.finditer(element_pattern, content, re.DOTALL)
                    
                    for match in element_matches:
                        element_content = match.group(1).strip()
                        
                        if isinstance(list_item_type, type) and issubclass(list_item_type, BaseModel):
                            # For BaseModel types, look for the class wrapper
                            class_pattern = rf'<{list_item_type.__name__.lower()}>(.*?)</{list_item_type.__name__.lower()}>'
                            class_match = re.search(class_pattern, element_content, re.DOTALL)
                            
                            if class_match:
                                # If wrapper found, parse its content
                                class_content = class_match.group(1)
                                item = response_from_xml(class_content, list_item_type, False)
                            else:
                                # If no wrapper, parse the direct content
                                item = response_from_xml(element_content, list_item_type, False)
                            items.append(item)
                        else:
                            # For basic types, use the content directly
                            items.append(list_item_type(element_content)) # TODO extract this to handle the same as above, not directly
                    
                    field_values[field_name] = items                
            
        print(f"\nCompleted parsing for {return_class.__name__}")
        return return_class(**field_values)
    except StructuredResponseException as e:
        raise StructuredResponseException(f"Error parsing XML for class {return_class.__name__}: {str(e)}", xml, return_class) from e


if __name__ == "__main__":        
    from datetime import date, datetime, time
    from rich import print as rprint
    from enum import Enum
    from typing import Dict, List, Optional, Union
    from pydantic import Field
    from llm_serv.structured_response.model import StructuredResponse    

    class AnEnum(Enum):
        TYPE1 = "type1"
        TYPE2 = "type2"

    class SubClassType1(StructuredResponse):
        sub_string: str = Field(default="", description="A sub string field")


    class SubClassType2(StructuredResponse):
        sub_list: List[str] | None = Field(default=[], description="A sub list of strings field")

    class SubClassType3(StructuredResponse):
        element1: SubClassType1 = Field(default=SubClassType1(), description="An element 1 field")
        element_sublist: List[SubClassType2] = Field(default=[], description="An element 2 list of sub class type 2 fields")

    class TestStructuredResponse(StructuredResponse):
        example_string: str = Field(default="", description="A string field")
        example_string_none: Optional[str] = Field(default=None, description="An optional string field")    
        example_int: int = Field(default=5, ge=0, le=10, description="An integer field with values between 0 and 10, default is 5")
        example_int_list: List[int] = Field(default=[1, 2, 3], description="A list of integers")
        example_enum: AnEnum = Field(default=AnEnum.TYPE1, description="An enum field with a custom description")
        example_float: float = Field(default=2.5, ge=0.0, le=5.0, description="A float field with values between 0.0 and 5.0, default is 2.5")
        example_list: List[SubClassType1] = Field(default=[SubClassType1()], description="A list of sub class type 1 fields")
        example_float_list_optional: Optional[List[float]] = Field(default=None, description="An optional list of floats")        
        example_optional_subclasstype1: Optional[SubClassType1] = Field(default=None, description="An optional sub class type 1 field")
        example_nested_subclasstype3: SubClassType3 = Field(default=SubClassType3(), description="A nested sub class type 3 field"),
        example_date: date = Field(description="A date field including month from 2023")
        example_datetime: datetime = Field(description="A full date time field from 2023")
        example_time: time = Field(description="A time field from today")
        example_list_of_subclasstype1: List[SubClassType1] = Field(default=[], description="A list of sub class type 1 fields")
        example_optional_list_of_subclasstype1: Optional[List[SubClassType1]] = Field(default=None, description="An optional list of sub class type 1 fields")


    xml_text = """```xml
    <structured_response>
    <example_string type='string'>[stringyyy  ]   s \t</example_string><example_int>2</example_int>    
    <example_int_list >
        <example_int_list_element type="integer">2</example_int_list_element>
        <example_int_list_element type="integer">3</example_int_list_element>
    </example_int_list>
    <example_enum type="enum">type2</example_enum>
    <example_float type="float">1.2</example_float>
    <example_float_list_optional type="float"></example_float_list_optional>
    <example_optional_subclasstype1 type="class"><!-- if null or not applicable leave this element empty -->
        <subclasstype1>
            <sub_string type="string"> another string </sub_string>
        </subclasstype1>
    </example_optional_subclasstype1>
    <example_nested_subclasstype3 type="class">
        <subclasstype3>
            <element1 type="class">
                <subclasstype1>
                    <sub_string type="string">[string]</sub_string>
                </subclasstype1>
            </element1>
            <element_sublist type="list">
                <element_sublist_element type="class">
                    <subclasstype2>
                        <sub_list type="list">
                            <sub_list_element type="string">[str]</sub_list_element>
                        </sub_list>
                    </subclasstype2>
                </element_sublist_element>                
            </element_sublist>
        </subclasstype3>
    </example_nested_subclasstype3>
    <example_int type="integer">2</example_int>
    <example_date type="date">20 Jan 2023</example_date>
    <example_datetime type="datetime">15.10.2023 12:00:00</example_datetime>
    <example_time type="time">3 PM</example_time>
            <example_list type="list">
        <example_list_element type="class">
            <subclasstype1>
                <sub_string type="string"> a 
                               
                string 
</sub_string>
            </subclasstype1>
        </example_list_element><example_list_element type="class">
            <subclasstype1><sub_string type="string">string 2</sub_string></subclasstype1></example_list_element></example_list>
    <example_optional_list_of_subclasstype1 type="list"><!-- if null or not applicable leave this element empty -->
        <example_optional_list_of_subclasstype1_element type="class">
            <subclasstype1>
                <sub_string type="string">[string 1]</sub_string>
            </subclasstype1>
        </example_optional_list_of_subclasstype1_element>

        <example_optional_list_of_subclasstype1_element type="class">
            <subclasstype1>
                <sub_string type="string">[string 2]</sub_string>
            </subclasstype1>
        </example_optional_list_of_subclasstype1_element>
    </example_optional_list_of_subclasstype1>

    <example_list_of_subclasstype1 type="list">
        <example_list_of_subclasstype1_element type="class">
            <subclasstype1>
                <sub_string type="string">non optional string for elem1</sub_string>
            </subclasstype1>
        </example_list_of_subclasstype1_element>

        <example_list_of_subclasstype1_element type="class">
            <subclasstype1>
                <sub_string type="string">non optional string for elem2</sub_string>
            </subclasstype1>
        </example_list_of_subclasstype1_element>
    </example_list_of_subclasstype1>
</structured_response> This is a complete example.```"""

    rprint(response_from_xml(xml_text, TestStructuredResponse))