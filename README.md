# Jim's Global Network (JGN)
[![Python CI](https://github.com/jim-wyatt/global-vpc/actions/workflows/python-app.yml/badge.svg)](https://github.com/jim-wyatt/global-vpc/actions/workflows/python-app.yml)    [![CodeQL](https://github.com/jim-wyatt/global-vpc/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/jim-wyatt/global-vpc/actions/workflows/github-code-scanning/codeql) [![Dependabot Updates](https://github.com/jim-wyatt/global-vpc/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/jim-wyatt/global-vpc/actions/workflows/dependabot/dependabot-updates) 

This script automates the creation and management of Virtual Private Clouds (VPCs) across multiple AWS regions. It begins by fetching all available AWS regions using the AWS SDK for Python (Boto3). For each region, the script creates a new VPC with a specified CIDR block, sets up security groups to control inbound and outbound traffic, and configures route tables to manage traffic routing. The script also creates subnets within each VPC, including public, private, data, and admin subnets, ensuring that each subnet is appropriately tagged and associated with the correct availability zone.

In addition to setting up individual VPCs, the script establishes VPC peering connections between the VPCs in different regions. This involves creating peering connections, accepting them, and configuring route tables to enable communication between the peered VPCs. The script uses concurrent processing to handle multiple regions simultaneously, significantly speeding up the VPC creation and peering process. Logging is used throughout the script to provide detailed information about the progress and status of the operations, making it easier to monitor and debug.

The main function orchestrates the entire process, starting with fetching the regions, creating and setting up VPCs in each region, and finally establishing peering connections between the VPCs. The script is designed to be run from the command line and requires AWS credentials to be configured. By automating these tasks, the script simplifies the management of a global network infrastructure, ensuring consistency and reducing the potential for human error.

<img width="1306" height="1149" alt="image" src="https://github.com/user-attachments/assets/6832a35f-8129-4749-bc93-7ebbcd71f3ac" />

This repository contains two main files: `global_vpc.py` and `test_global_vpc.py`. Below is a detailed description of each file and its contents.

## global_vpc.py

This file contains the main logic for creating and managing VPCs across multiple AWS regions. It includes the following functions:

- `get_all_regions()`: Fetches all available AWS regions.
- `create_vpc_in_region(region, cidr_block)`: Creates a VPC in the specified region with the given CIDR block.
- `setup_vpc(vpc_id, region)`: Sets up the VPC by creating an internet gateway and attaching it to the VPC.
- `setup_security_groups(ec2, vpc)`: Sets up security groups for the VPC.
- `setup_route_tables(vpc, gateway_id)`: Sets up route tables for the VPC.
- `process_region(region, cidr_block)`: Processes a region by creating and setting up a VPC.
- `create_subnets(vpc, cidr_block, availability_zones)`: Creates subnets in the given VPC.
- `create_peering(requestor, acceptor)`: Creates VPC peering connections between the VPCs in different regions.
- `main()`: Orchestrates the entire process of fetching regions, creating and setting up VPCs, and establishing peering connections.

Exception handling is implemented throughout the script to handle errors gracefully and provide informative error messages.

## test_global_vpc.py

This file contains a suite of unit tests for the functions in `global_vpc.py`. The tests use the `unittest` framework and the `unittest.mock` library to mock AWS SDK calls and other dependencies. The tests cover the following functions:

- `test_get_all_regions()`: Tests the `get_all_regions` function, including error handling.
- `test_create_vpc_in_region()`: Tests the `create_vpc_in_region` function, including error handling.
- `test_setup_vpc()`: Tests the `setup_vpc` function, including error handling.
- `test_setup_security_groups()`: Tests the `setup_security_groups` function, including error handling.
- `test_setup_route_tables()`: Tests the `setup_route_tables` function, including error handling.
- `test_process_region()`: Tests the `process_region` function, including error handling.
- `test_create_subnets()`: Tests the `create_subnets` function, including error handling.
- `test_create_peering()`: Tests the `create_peering` function, including error handling.
- `test_main()`: Tests the `main` function.

These tests ensure that the functions work as expected and handle errors gracefully, improving the overall reliability of the script.

### Usage

To use the script, you need to have the necessary cloud provider credentials and permissions. The script can be executed from the command line:

```bash
python global_vpc.py
```

## test_global_vpc.py

`test_global_vpc.py` contains unit tests for the functions defined in `global_vpc.py`. The tests ensure that the VPC creation and configuration functions work as expected.

### Key Tests

- **test_create_vpc()**: Verifies that the VPC is created with the correct parameters.
- **test_configure_subnets()**: Checks that subnets are configured correctly within the VPC.
- **test_setup_security_groups()**: Ensures that security groups are set up with the correct rules.
- **test_create_route_tables()**: Validates that route tables are created and associated with subnets properly.

### Running Tests

To run the tests, you can use a test runner like `pytest`. Execute the following command in the terminal:

```bash
pytest test_global_vpc.py
```

## Requirements

- Python 3.x
- `boto3` library for AWS interactions
- `pytest` for running tests

## Installation

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

## Contributing

Contributions are welcome! Please fork the repository and create a pull request with your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
