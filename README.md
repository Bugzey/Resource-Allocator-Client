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


###	`resource_allocator_client`
```
usage: resource_allocator_client [-h] -s SERVER -e EMAIL [-p PASSWORD] [-a]
                                 {register,login,list,get,create,delete,update,query}
                                 ...

Command-line client to query the Resource-Allocator API application

options:
  -h, --help            show this help message and exit
  -s SERVER, --server SERVER
                        Server address
  -e EMAIL, --email EMAIL
                        User email
  -p PASSWORD, --password PASSWORD
                        User password. Leave blank for interactive entry
  -a, --azure-login     Log-in via Azure AD

subcommands:
  {register,login,list,get,create,delete,update,query}
```

Each subcommand - register, login ,list, get, create, update, query has its own additional arguments
such as id or KEY=VALUE pairs.


###	`resource_allocator_client register`
```
usage: resource_allocator_client register [-h] [KEY=VALUE ...]

positional arguments:
  KEY=VALUE   Key-value pairs to create, update or query

options:
  -h, --help  show this help message and exit
```

###	`resource_allocator_client list`
```
usage: resource_allocator_client list [-h]
                                      {resources,resource_groups,resource_to_group,iterations,requests,allocation}

positional arguments:
  {resources,resource_groups,resource_to_group,iterations,requests,allocation}

options:
  -h, --help            show this help message and exit

```


###	`resource_allocator_client get`
```
usage: resource_allocator_client get [-h]
                                     {resources,resource_groups,resource_to_group,iterations,requests,allocation}
                                     id

positional arguments:
  {resources,resource_groups,resource_to_group,iterations,requests,allocation}
  id                    ID of the item

options:
  -h, --help            show this help message and exit
```


###	`resource_allocator_client create`
```
usage: resource_allocator_client create [-h]
                                        {resources,resource_groups,resource_to_group,iterations,requests,allocation}
                                        [KEY=VALUE ...]

positional arguments:
  {resources,resource_groups,resource_to_group,iterations,requests,allocation}
  KEY=VALUE             Key-value pairs to create, update or query

options:
  -h, --help            show this help message and exit
```


###	`resource_allocator_client delete`
```
usage: resource_allocator_client delete [-h]
                                        {resources,resource_groups,resource_to_group,iterations,requests,allocation}
                                        id

positional arguments:
  {resources,resource_groups,resource_to_group,iterations,requests,allocation}
  id                    ID of the item

options:
  -h, --help            show this help message and exit
```

###	`resource_allocator_client update`
```
usage: resource_allocator_client update [-h]
                                        {resources,resource_groups,resource_to_group,iterations,requests,allocation}
                                        id [KEY=VALUE ...]

positional arguments:
  {resources,resource_groups,resource_to_group,iterations,requests,allocation}
  id                    ID of the item
  KEY=VALUE             Key-value pairs to create, update or query

options:
  -h, --help            show this help message and exit
```


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
