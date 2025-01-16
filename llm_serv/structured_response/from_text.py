from typing import Type, get_origin, get_args, Union, List, Optional
from enum import Enum
from pydantic import BaseModel
from datetime import date as date_type, datetime as datetime_type, time as time_type
import dateparser
import re

def response_from_xml(xml: str, return_class: Type['StructuredResponse'], is_root: bool = True, exclude_fields: List[str] = []) -> 'StructuredResponse':
    # Remove XML comments
    xml = re.sub(r'<!--.*?-->', '', xml, flags=re.DOTALL)

    if is_root:
        response_match = re.search(r'<response>(.*?)</response>', xml, re.DOTALL)
        if response_match:
            xml = response_match.group(1)
        else:
            xml = xml.replace('<response>', '').replace('</response>', '')

    field_values = {}
    for field_name, field_info in return_class.model_fields.items():
        if field_name in exclude_fields:
            continue

        field_type = field_info.annotation
        original_type = field_type

        is_optional = False
        if get_origin(field_type) is Union and type(None) in get_args(field_type):
            is_optional = True
            field_type = next(arg for arg in get_args(field_type) if arg != type(None))

        pattern = rf'<{field_name}>(.*?)</{field_name}>'
        match = re.search(pattern, xml, re.DOTALL | re.IGNORECASE)

        if not match:
            if is_optional:
                field_values[field_name] = None
                continue
            else:
                raise ValueError(f"Required field '{field_name}' not found in the XML input")

        content = match.group(1).strip()
        if not content and is_optional:
            field_values[field_name] = None
            continue

        if get_origin(original_type) is Union:
            args = get_args(original_type)
            success = False
            for arg in args:
                if arg is type(None):
                    continue
                try:
                    if isinstance(arg, type) and issubclass(arg, BaseModel):
                        class_pattern = rf'<{arg.__name__.lower()}>(.*?)</{arg.__name__.lower()}>'
                        class_match = re.search(class_pattern, content, re.DOTALL)
                        if class_match:
                            field_values[field_name] = response_from_xml(class_match.group(1), arg, False)
                            success = True
                            break
                    elif get_origin(arg) is list:
                        # Handle List types within Union
                        element_type = get_args(arg)[0]
                        elements = []
                        element_pattern = rf'<{field_name}_element>(.*?)</{field_name}_element>'
                        element_matches = re.finditer(element_pattern, content, re.DOTALL)
                        
                        for element_match in element_matches:
                            element_content = element_match.group(1).strip()
                            if isinstance(element_type, type) and issubclass(element_type, BaseModel):
                                elements.append(response_from_xml(element_content, element_type, False))
                            else:
                                elements.append(element_type(element_content))
                        
                        field_values[field_name] = elements
                        success = True
                        break
                    else:
                        field_values[field_name] = arg(content)
                        success = True
                        break
                except (ValueError, TypeError) as e:
                    #print(f"Error parsing Union field {field_name} with content: {content}")
                    #print(f"Error: {e}")
                    continue

            if not success and not is_optional:
                raise ValueError(f"Could not parse Union field {field_name} with content: {content}")
            continue

        if get_origin(field_type) is list:
            element_type = get_args(field_type)[0]
            print(f"\nProcessing list field: {field_name}")
            print(f"Element type: {element_type.__name__}")
            elements = []

            # Try both patterns - with and without the _experience suffix
            base_name = field_name.replace('_experience', '')
            patterns = [
                rf'<{field_name}_element>(.*?)</{field_name}_element>',
                rf'<{base_name}_element>(.*?)</{base_name}_element>'
            ]
            
            matches = []
            for pattern in patterns:
                element_matches = re.finditer(pattern, content, re.DOTALL)
                matches.extend(list(element_matches))
            
            print(f"Found {len(matches)} matches")

            for element_match in matches:
                element_content = element_match.group(1).strip()
                print(f"Element content: {element_content}")
                if isinstance(element_type, type) and issubclass(element_type, BaseModel):
                    class_pattern = rf'<{element_type.__name__.lower()}>(.*?)</{element_type.__name__.lower()}>'
                    print(f"Looking for pattern: {class_pattern}")
                    class_match = re.search(class_pattern, element_content, re.DOTALL)
                    if class_match:
                        element_content = class_match.group(1)
                        print(f"Found match, extracted: {element_content[:100]}...")
                    else:
                        print("No match found!")
                    elements.append(response_from_xml(element_content, element_type, False))
                else:
                    elements.append(element_type(element_content))

            field_values[field_name] = elements if elements else None
            continue

        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            class_pattern = rf'<{field_type.__name__.lower()}>(.*?)</{field_type.__name__.lower()}>'
            class_match = re.search(class_pattern, content, re.DOTALL)
            if class_match:
                field_values[field_name] = response_from_xml(class_match.group(1), field_type, False)
            else:
                field_values[field_name] = response_from_xml(content, field_type, False)
            continue

        if isinstance(field_type, type) and issubclass(field_type, Enum):
            field_values[field_name] = field_type(content)
            continue

        if field_type in (date_type, datetime_type, time_type):
            try:
                parsed_date = dateparser.parse(content)
                if not parsed_date:
                    raise ValueError(f"Could not parse date/time string: {content}")

                if field_type is date_type:
                    field_values[field_name] = parsed_date.date()
                elif field_type is time_type:
                    field_values[field_name] = parsed_date.time()
                else:
                    field_values[field_name] = parsed_date
                continue
            except Exception as e:
                raise ValueError(f"Failed to parse {field_type.__name__} field {field_name} with content '{content}': {str(e)}")

        try:
            field_values[field_name] = field_type(content)
        except ValueError as e:
            raise ValueError(f"Failed to parse field {field_name} with content '{content}': {str(e)}")

    return return_class(**field_values)

def response_from_json(json: str, is_root: bool = True) -> 'StructuredResponse':
    pass