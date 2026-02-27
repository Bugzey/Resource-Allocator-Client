#	Resource Allocator Client

##	Description

This repository contains a command-line client to the [Resource Allocator] project. Main features:

* user creation and logging in with token caching
* create, list, get, update, delete all object types


##	Installation

Install using build and pip:

```
pip install build
pip install .
```


##	Usage

The application can be executed as a Python runnable module or as a standalone command-line
application:

```
usage: resource_allocator_client [-h] -s SERVER -e EMAIL [-t TIMEOUT] [-p PASSWORD | -a] [-c CACHE]
                                 {register,login,allocations,images,image_properties,iterations,requests,resource_groups,resource_to_group,resources,users}
                                 ...

Command-line client to query the Resource-Allocator API application

options:
  -h, --help            show this help message and exit
  -s SERVER, --server SERVER
                        Server address
  -e EMAIL, --email EMAIL
                        User email
  -t TIMEOUT, --timeout TIMEOUT
                        Request timeout
  -p PASSWORD, --password PASSWORD
                        User password. Leave blank for interactive entry
  -a, --azure-login     Log-in via Azure AD
  -c CACHE, --cache CACHE
                        Path to a custom login cache file

subcommands:
  {register,login,allocations,images,image_properties,iterations,requests,resource_groups,resource_to_group,resources,users}
```

Each resources has its own command. Most have CRUD (create, read, update, delete) operations with
some additional endpoints. Below you will find examples for the `register`, `login` and all actions
for the `requests` resource.


###	`resource_allocator_client register`

```
usage: resource_allocator_client register [-h] [KEY=VALUE ...]

positional arguments:
  KEY=VALUE   Key-value pairs to create, update or query

options:
  -h, --help  show this help message and exit
```


### `resource_allocator_client login`

```
usage: resource_allocator_client login [-h]

options:
  -h, --help  show this help message and exit
```

###	`resource_allocator_client requests`

```
usage: resource_allocator_client requests [-h] [-l LIMIT] [-o OFFSET] [--order-by ORDER_BY] [--id ID]
                                          {create,get,list,query,update,delete,approve,decline}
                                          [KEY=VALUE ...]

positional arguments:
  {create,get,list,query,update,delete,approve,decline}
  KEY=VALUE             Key-value pairs to create, update or query

options:
  -h, --help            show this help message and exit
  -l LIMIT, --limit LIMIT
                        Number of items to return
  -o OFFSET, --offset OFFSET
                        Offset total result set
  --order-by ORDER_BY   Comma-separated list of columns to order the result set by. Add '-' in front of
                        a colum name for descending order
  --id ID               Resource identifier if needed
```


###	Special Keys

Some attributes are handled in a different way depending on the key used. The keys are not limited
to an action or to a resource type:

* image - the input is a path to an image file. It is read and encoded in base64 before being sent
  to the server


##	Contributing

New functionality should be added via creating feature or bug fix branches and issuing a pull
request. Any new functionality should come with unit tests written with the built-in `unittest`
library.


##	Project Status:

- [ ] Planning
- [ ] Prototype
- [X] In Development
- [ ] In Production
- [ ] Unsupported
- [ ] Retired


##	Authors and Acknowledgement

README based on <https://www.makeareadme.com/>


[Resource Allocator]: https://github.com/Bugzey/Resource-Allocator
