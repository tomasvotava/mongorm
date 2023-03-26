# MongORM

![MongORM](./banner.png)

`MongORM` is an ORM (object relational mapping) wrapper using async library motor for `MongoDB` connection and pydantic for data definition and validation.

**This module is a work in progress and API may change radically.**

`MongORM` uses [`pydantic`](https://docs.pydantic.dev/) for data validation
and [`motor`](https://www.mongodb.com/docs/drivers/motor/) for async MongoDB connection.

## Installation

Using PIP:

```console
pip install python-mongorm
```

Using poetry:

```console
poetry add python-mongorm
```

## Usage

### Create client

```python
from mongorm import MongORM

client = MongORM("mongodb://root:root@localhost:27017/", "database")
```

### Define model

```python
from mongorm import BaseModel, MongoIndex, MongoIndexType

class Book(BaseModel):
    """Define models the way you would define pydantic models"""

    class Meta:
        """Meta contains the model's configuration and indexes"""
        client = client  # pass the client to the model's Meta
        collection = "books"
        title = MongoIndex("title", MongoIndexType.ASCENDING)
        author = MongoIndex("author", MongoIndexType.ASCENDING)
    
    # id field of type ObjectId is created automatically
    title: str
    author: str
    year_published: int

```
