"""
This test file is for testing the StructuredResponse class with all complex types.
"""

from datetime import date, datetime, time
from enum import Enum
from rich import print as rprint
from typing import Dict, List, Optional
from pydantic import Field

from llm_serv.structured_response.model import StructuredResponse


class AnEnum(Enum):
    TYPE1 = "type1"
    TYPE2 = "type2"

class SubClassType1(StructuredResponse):
    sub_string: str = Field(default="", description="A sub string field")


class SubClassType2(StructuredResponse):
    sub_list: Optional[List[str]] = Field(default=None, description="A sub list of strings field")

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
    example_optional_list_of_subclasstype1: Optional[List[SubClassType1]] = Field(default=None, description="An optional list of sub class type 1 fields")

if __name__ == "__main__":
    print("Testing StructuredResponse with all complex types")
    xml_text = TestStructuredResponse.to_text(exclude_fields=["example_int"])
    
    print(xml_text)

    xml_text = """```xml
    <response>
    <example_string type="string">[string]</example_string><example_int>2</example_int>    
    <example_int_list  type="list">
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
</response> This is a complete example.```"""

    print("\n"+"="*120)
    print("Testing StructuredResponse from XML")
    print("="*120)
    response = TestStructuredResponse.from_text(xml_text)
    rprint(response)
    


