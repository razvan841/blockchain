from ipv8.messaging.payload_dataclass import DataClassPayload, convert_to_payload, type_from_format
from dataclasses import dataclass


varlenHutf8 = type_from_format("varlenHutf8")
uint64 = type_from_format("Q")


@dataclass
class SubmitMessage(DataClassPayload[1]):
    email: str
    github_url:  str
    nonce: int

@dataclass
class ResponseMessage(DataClassPayload[2]):
    success: bool 
    message: str

convert_to_payload(SubmitMessage)
convert_to_payload(ResponseMessage)