# MIT License
#
# Copyright (c) 2025 Jim Wyatt <jim at wyattconsulting dot com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import boto3
import logging
import concurrent.futures
from typing import List
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="global_vpc.log",
)

# Magic numbers
SUBNET_OFFSET = 4
SUBNET_WIDTH = 22
REGION_SUBNET_START = 101
PUBLIC_SUBNET_START = 11
PRIVATE_SUBNET_START = 51
DATA_SUBNET_START = 101
ADMIN_SUBNET_START = 201


def get_all_regions() -> List[str]:
    """Fetch all AWS regions.

    Returns:
        List[str]: A list of all AWS region names.
    """
    logging.info("Fetching all AWS regions")
    try:
        ec2 = boto3.client("ec2")
        all_regions = ec2.describe_regions()
        regions = [region["RegionName"] for region in all_regions["Regions"]]
        regions.sort()
        logging.info(f"Regions fetched: {regions}")
        return regions
    except ClientError as e:
        logging.error(f"Error fetching regions: {e}")
        return []


def create_vpc_in_region(region, cidr_block) -> str:
    """Create a VPC in the specified region with the given CIDR block.

    Args:
        region (str): The AWS region where the VPC will be created.
        cidr_block (str): The CIDR block for the VPC.

    Returns:
        str: The ID of the created VPC.
    """
    try:
        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.create_vpc(
            CidrBlock=cidr_block,
            TagSpecifications=[
                {
                    "ResourceType": "vpc",
                    "Tags": [{"Key": "Name", "Value": f"vpc-{region}-jgn"}],
                }
            ],
        )
        vpc_id = response["Vpc"]["VpcId"]
        ec2.get_waiter("vpc_available").wait(VpcIds=[vpc_id])
        return vpc_id
    except ClientError as e:
        logging.error(f"Error creating VPC in region {region}: {e}")
        return ""


def setup_vpc(vpc_id, region) -> tuple:
    """Set up the VPC by creating and attaching an internet gateway.

    Args:
        vpc_id: The ID of the VPC.
        region: The AWS region where the VPC is located.

    Returns:
        tuple: The VPC object and the ID of the internet gateway.
    """
    try:
        ec2 = boto3.resource("ec2", region_name=region)
        vpc = ec2.Vpc(vpc_id)  # type: ignore[attr-defined]
        gateway = ec2.create_internet_gateway(  # type: ignore[attr-defined]
            TagSpecifications=[
                {
                    "ResourceType": "internet-gateway",
                    "Tags": [
                        {"Key": "Name", "Value": f"igw-{region}-jgn"},
                    ],
                },
            ]
        )
        vpc.attach_internet_gateway(InternetGatewayId=gateway.id)
        return vpc, gateway.id
    except ClientError as e:
        logging.error(f"Error setting up VPC {vpc_id} in region {region}: {e}")
        return None, None


def setup_security_groups(ec2, vpc) -> None:
    """Set up security groups for the given VPC.

    Args:
        ec2: The EC2 client object.
        vpc: The VPC object.

    Returns:
        None
    """
    try:
        for sg in vpc.security_groups.all():
            ec2.authorize_security_group_ingress(
                GroupId=sg.id,
                IpPermissions=[
                    {
                        "IpProtocol": "icmp",
                        "FromPort": -1,
                        "ToPort": -1,
                        "IpRanges": [{"CidrIp": "10.0.0.0/8"}],
                    }
                ],
            )
    except ClientError as e:
        logging.error(f"Error setting up security groups for VPC {vpc.id}: {e}")


def setup_route_tables(vpc, gateway_id) -> None:
    """Set up route tables for the given VPC.

    Args:
        vpc: The VPC object.
        gateway_id: The ID of the internet gateway.

    Returns:
        None
    """
    try:
        for route_table in vpc.route_tables.all():
            vpc.create_tags(
                Resources=[route_table.id],
                Tags=[
                    {
                        "Key": "Name",
                        "Value": f"rtb-{vpc.meta.client.meta.region_name}-jgn",
                    }
                ],
            )
            route_table.create_route(
                DestinationCidrBlock="0.0.0.0/0", GatewayId=gateway_id
            )
    except ClientError as e:
        logging.error(f"Error setting up route tables for VPC {vpc.id}: {e}")


def process_region(region, cidr_block) -> dict:
    """Process a region by creating a VPC, setting up security groups, route tables, and subnets.

    Args:
        region (str): The AWS region to process.
        cidr_block (int): The CIDR block to use for the VPC.

    Returns:
        dict: Information about the processed region, including Region, VpcId, and Cidr.
    """
    try:
        cidr = f"10.{cidr_block}.0.0/16"
        vpc_id = create_vpc_in_region(region, cidr)

        if vpc_id:
            vpc, gateway_id = setup_vpc(vpc_id, region)
            setup_security_groups(boto3.client("ec2", region_name=region), vpc)
            setup_route_tables(vpc, gateway_id)

            availability_zones = boto3.client(
                "ec2", region_name=region
            ).describe_availability_zones()["AvailabilityZones"]

            subnets = create_subnets(vpc, cidr_block, availability_zones)

            logging.info(f"Region {region} processed - {len(subnets)} subnets created")

            return {"Region": region, "VpcId": vpc_id, "Cidr": cidr}
        else:
            return dict()
    except ClientError as e:
        logging.error(f"Error processing region {region}: {e}")
        return dict()


def create_subnets(vpc, cidr_block, availability_zones) -> List:
    """Create subnets in the given VPC.

    Args:
        vpc: The VPC object.
        cidr_block: The CIDR block to use for the subnets.
        availability_zones: List of availability zones in the region.

    Returns:
        List: A list of created subnets.
    """
    try:
        subnets = []
        for index, az in enumerate(availability_zones):
            for subnet_type, subnet_start in [
                ["public", PUBLIC_SUBNET_START],
                ["private", PRIVATE_SUBNET_START],
                ["data", DATA_SUBNET_START],
                ["admin", ADMIN_SUBNET_START],
            ]:
                subnet_cidr = index * SUBNET_OFFSET + subnet_start
                subnet = vpc.create_subnet(
                    CidrBlock=f"10.{cidr_block}.{subnet_cidr}.0/{SUBNET_WIDTH}",
                    AvailabilityZone=az["ZoneName"],
                    TagSpecifications=[
                        {
                            "ResourceType": "subnet",
                            "Tags": [
                                {
                                    "Key": "Name",
                                    "Value": f"subnet-{az['ZoneId']}-{subnet_type[:3]}-jgn",
                                }
                            ],
                        }
                    ],
                )
                subnets.append(subnet)

                logging.info(f"{subnet.subnet_id} - {subnet.cidr_block} created")
        return subnets
    except ClientError as e:
        logging.error(f"Error creating subnets in VPC {vpc.id}: {e}")
        return list()


def create_peering(requestor, acceptor) -> None:
    """Create a VPC peering connection between two VPCs.

    Args:
        requestor: A dictionary containing information about the requesting VPC.
        acceptor: A dictionary containing information about the accepting VPC.

    Returns:
        None
    """
    try:
        vpc1 = boto3.resource("ec2", region_name=requestor["Region"]).Vpc(  # type: ignore[attr-defined]
            requestor["VpcId"]
        )
        target_region_resource = boto3.resource("ec2", region_name=acceptor["Region"])
        vpc2 = target_region_resource.Vpc(acceptor["VpcId"])  # type: ignore[attr-defined]

        peering_connection = vpc1.request_vpc_peering_connection(
            PeerVpcId=acceptor["VpcId"],
            PeerRegion=acceptor["Region"],
            TagSpecifications=[
                {
                    "ResourceType": "vpc-peering-connection",
                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": f"pcx-{requestor['Region']}-{acceptor['Region']}-jgn",
                        },
                    ],
                },
            ],
        )

        # Get the request from the target VPC, wait until it exists, and accept
        vpc_peering_connection_accepter = target_region_resource.VpcPeeringConnection(  # type: ignore[attr-defined]
            peering_connection.vpc_peering_connection_id
        )

        logging.info(
            f"Peering between {requestor['Region']} and {acceptor['Region']} requested"
        )

        vpc_peering_connection_accepter.wait_until_exists(
            Filters=[
                {
                    "Name": "vpc-peering-connection-id",
                    "Values": [peering_connection.vpc_peering_connection_id],
                }
            ]
        )

        vpc_peering_connection_accepter.accept()
        logging.info(
            f"Peering between {requestor['Region']} and {acceptor['Region']} successful"
        )

        # Have to go back and set the tag from the target VPC side
        ec2_client = boto3.client("ec2", region_name=acceptor["Region"])
        ec2_client.create_tags(
            Resources=[peering_connection.vpc_peering_connection_id],
            Tags=[
                {
                    "Key": "Name",
                    "Value": f"pcx-{requestor['Region']}-{acceptor['Region']}-jgn",
                }
            ],
        )

        # Update route tables and set their names by tag api in both VPCs.
        # Only one route table per vpc exists, but have to get an iterable.
        for route_table in vpc2.route_tables.all():
            route_table.create_route(
                DestinationCidrBlock=requestor["Cidr"],
                VpcPeeringConnectionId=peering_connection.id,
            )

        for route_table in vpc1.route_tables.all():
            route_table.create_route(
                DestinationCidrBlock=acceptor["Cidr"],
                VpcPeeringConnectionId=peering_connection.id,
            )

        logging.info(
            f"Routing tables in {requestor['Region']} and {acceptor['Region']} updated"
        )
    except ClientError as e:
        logging.error(f"Error creating VPC peering: {e}")


def main() -> None:
    """Main function to orchestrate the VPC creation and peering.

    This function fetches all AWS regions, creates VPCs in each region,
    sets up security groups, route tables, subnets, and establishes VPC peering connections.
    It prompts the user for confirmation before proceeding with the operations.
    """

    # Prompt the user for confirmation
    confirmation = input(
        """Global VPC (jgn) - IaGP Demonstrator
This script will:

    - create a VPC in each region with the CIDR block 10.[region].0.0/16

    - create four /22 subnets in each availability zone per VPC:

        - public -> publically accessible resources
        - private -> private resources, accessible from public subnets
        - data -> data resources, accessible from private subnets
        - admin -> administraive resources, can access all other subnets

    - create a VPC peering connection between each pair of VPCs

    - update routing tables to allow traffic between the VPCs

    - set up security groups to allow ICMP traffic between the VPCs

    - tag all resources with the appropriate names

Are you sure you want to proceed with the VPC creation and peering process? (yes/no): """
    )

    if confirmation.lower() != "yes":
        logging.info("Operation cancelled by the user.")
        return

    logging.info("Starting VPC creation and peering process")

    try:
        regions = get_all_regions()
        region_subnet = REGION_SUBNET_START
        vpcs = []

        # Concurrently processes multiple regions by creating and setting up VPCs in each region.
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_region = {
                executor.submit(
                    process_region, region, region_subnet + i * SUBNET_OFFSET
                ): region
                for i, region in enumerate(regions)
            }
            for future in concurrent.futures.as_completed(future_to_region):
                region = future_to_region[future]
                try:
                    vpcs.append(future.result())
                except Exception as e:
                    logging.error(f"Error processing region {region}: {e}")

        # Concurrently establishes VPC peering connections between all VPCs.
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(create_peering, requestor, acceptor)
                for idx, requestor in enumerate(vpcs)
                for acceptor in vpcs[idx + 1 :]
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        logging.info("VPC creation and peering process completed successfully.")

    except ClientError as e:
        logging.error(f"Error in main execution: {e}")


if __name__ == "__main__":
    main()
