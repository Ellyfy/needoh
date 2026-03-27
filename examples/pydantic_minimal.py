"""Minimal Pydantic example.

This script demonstrates how to define a simple Pydantic model with a single string field
and instantiate it. It is intentionally short (under 25 lines) and runnable.
"""

from pydantic import BaseModel

class Person(BaseModel):
    """A minimal model with a single string field."""
    name: str

if __name__ == "__main__":
    # Create an instance of the model
    person = Person(name="Alice")
    # Print the model and the field value
    print(person)
    print("Name:", person.name)
