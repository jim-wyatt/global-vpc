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

import unittest
from unittest.mock import patch, MagicMock
import global_vpc
from botocore.exceptions import ClientError


class TestGlobalVPC(unittest.TestCase):
    @patch("global_vpc.boto3.client")
    def test_get_all_regions(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_regions.return_value = {
            "Regions": [{"RegionName": "us-east-1"}, {"RegionName": "us-west-1"}]
        }

        regions = global_vpc.get_all_regions()
        self.assertEqual(regions, ["us-east-1", "us-west-1"])

        # Test error handling
        mock_ec2.describe_regions.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "DescribeRegions"
        )
        regions = global_vpc.get_all_regions()
        self.assertEqual(regions, [])

    @patch("global_vpc.boto3.client")
    def test_create_vpc_in_region(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.create_vpc.return_value = {"Vpc": {"VpcId": "vpc-12345"}}
        mock_ec2.get_waiter.return_value.wait.return_value = None

        vpc_id = global_vpc.create_vpc_in_region("us-east-1", "10.0.0.0/16")
        self.assertEqual(vpc_id, "vpc-12345")

        # Test error handling
        mock_ec2.create_vpc.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateVpc"
        )
        vpc_id = global_vpc.create_vpc_in_region("us-east-1", "10.0.0.0/16")
        self.assertIsNone(vpc_id)

    @patch("global_vpc.boto3.client")
    @patch("global_vpc.boto3.resource")
    def test_setup_vpc(self, mock_boto_resource, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2_resource = MagicMock()
        mock_boto_resource.return_value = mock_ec2_resource
        mock_vpc = MagicMock()
        mock_ec2_resource.Vpc.return_value = mock_vpc
        mock_gateway = MagicMock()
        mock_ec2_resource.create_internet_gateway.return_value = mock_gateway

        vpc_id = "vpc-12345"
        region = "us-east-1"

        vpc, gateway_id = global_vpc.setup_vpc(vpc_id, region)
        self.assertEqual(vpc, mock_vpc)
        self.assertEqual(gateway_id, mock_gateway.id)

        # Test error handling
        mock_ec2_resource.create_internet_gateway.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateInternetGateway"
        )
        vpc, gateway_id = global_vpc.setup_vpc(vpc_id, region)
        self.assertIsNone(vpc)
        self.assertIsNone(gateway_id)

    @patch("global_vpc.boto3.client")
    def test_setup_security_groups(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_vpc = MagicMock()
        mock_vpc.security_groups.all.return_value = [MagicMock(id="sg-12345")]

        global_vpc.setup_security_groups(mock_ec2, mock_vpc)

        mock_ec2.authorize_security_group_ingress.assert_called_once_with(
            GroupId="sg-12345",
            IpPermissions=[
                {
                    "IpProtocol": "icmp",
                    "FromPort": -1,
                    "ToPort": -1,
                    "IpRanges": [{"CidrIp": "10.0.0.0/8"}],
                }
            ],
        )

        # Test error handling
        mock_ec2.authorize_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "AuthorizeSecurityGroupIngress"
        )
        global_vpc.setup_security_groups(mock_ec2, mock_vpc)

    @patch("global_vpc.boto3.client")
    def test_setup_route_tables(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_vpc = MagicMock()
        mock_vpc.route_tables.all.return_value = [MagicMock()]

        gateway_id = "igw-12345"
        global_vpc.setup_route_tables(mock_vpc, gateway_id)

        mock_vpc.route_tables.all.return_value[0].create_route.assert_called_once_with(
            DestinationCidrBlock="0.0.0.0/0", GatewayId=gateway_id
        )

        # Test error handling
        mock_vpc.route_tables.all.return_value[
            0
        ].create_route.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateRoute"
        )
        global_vpc.setup_route_tables(mock_vpc, gateway_id)

    @patch("global_vpc.boto3.client")
    def test_process_region(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_availability_zones.return_value = {
            "AvailabilityZones": [{"ZoneId": "az1"}, {"ZoneId": "az2"}]
        }
        mock_vpc = MagicMock()
        mock_vpc.create_subnet = MagicMock()

        with (
            patch("global_vpc.create_vpc_in_region", return_value="vpc-12345"),
            patch("global_vpc.setup_vpc", return_value=(mock_vpc, "igw-12345")),
            patch("global_vpc.create_subnets") as mock_create_subnets,
        ):
            global_vpc.process_region("us-east-1", "10.0.0.0/16")
            mock_create_subnets.assert_called_once()

        # Test error handling
        with patch("global_vpc.create_vpc_in_region", return_value=None):
            global_vpc.process_region("us-east-1", "10.0.0.0/16")

    @patch("global_vpc.boto3.client")
    def test_create_vpc_peering(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_vpc = MagicMock()
        mock_vpc.request_vpc_peering_connection.return_value = MagicMock(
            vpc_peering_connection_id="pcx-12345"
        )
        mock_vpc.route_tables.all.return_value = [MagicMock()]

        vpcs = [
            {"Region": "us-east-1", "VpcId": "vpc-12345", "Cidr": "10.0.0.0/16"},
            {"Region": "us-west-1", "VpcId": "vpc-67890", "Cidr": "10.1.0.0/16"},
        ]

        with patch(
            "global_vpc.boto3.resource",
            return_value=MagicMock(Vpc=MagicMock(return_value=mock_vpc)),
        ):
            global_vpc.create_peering(vpcs[0], vpcs[1])
            mock_vpc.route_tables.all.return_value[0].create_route.assert_called()

    @patch("global_vpc.boto3.client")
    @patch("builtins.input", side_effect=["no"])
    def test_main_cancelled(self, mock_input, mock_boto_client):
        with (
            patch("global_vpc.get_all_regions"),
            patch("global_vpc.process_region"),
            patch("global_vpc.create_peering"),
        ):
            global_vpc.main()
            global_vpc.process_region.assert_not_called()
            global_vpc.create_peering.assert_not_called()

    @patch("global_vpc.boto3.client")
    def test_create_subnets(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_vpc = MagicMock()
        mock_vpc.create_subnet = MagicMock()

        availability_zones = [
            {"ZoneName": "us-east-1a", "ZoneId": "use1-az1"},
            {"ZoneName": "us-west-2b", "ZoneId": "usw2-az2"},
        ]
        cidr_block = 0

        subnets = global_vpc.create_subnets(mock_vpc, cidr_block, availability_zones)

        expected_calls = [
            ("10.0.8.0/22", "us-east-1a"),
            ("10.0.72.0/22", "us-east-1a"),
            ("10.0.136.0/22", "us-east-1a"),
            ("10.0.200.0/22", "us-east-1a"),
            ("10.0.12.0/22", "us-west-2b"),
            ("10.0.76.0/22", "us-west-2b"),
            ("10.0.140.0/22", "us-west-2b"),
            ("10.0.204.0/22", "us-west-2b"),
        ]

        actual_calls = [
            (call[1]["CidrBlock"], call[1]["AvailabilityZone"])
            for call in mock_vpc.create_subnet.call_args_list
        ]

        self.assertEqual(actual_calls, expected_calls)
        self.assertEqual(len(subnets), 8)

        # Test error handling
        mock_vpc.create_subnet.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateSubnet"
        )
        subnets = global_vpc.create_subnets(mock_vpc, cidr_block, availability_zones)
        self.assertIsNone(subnets)

    @patch("global_vpc.boto3.client")
    def test_get_all_regions_error_handling(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_regions.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "DescribeRegions"
        )

        regions = global_vpc.get_all_regions()
        self.assertEqual(regions, [])

    @patch("global_vpc.boto3.client")
    def test_create_vpc_in_region_error_handling(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.create_vpc.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateVpc"
        )

        vpc_id = global_vpc.create_vpc_in_region("us-east-1", "10.0.0.0/16")
        self.assertIsNone(vpc_id)

    @patch("global_vpc.boto3.resource")
    def test_setup_vpc_error_handling(self, mock_boto_resource):
        mock_ec2_resource = MagicMock()
        mock_boto_resource.return_value = mock_ec2_resource
        mock_ec2_resource.create_internet_gateway.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateInternetGateway"
        )

        vpc, gateway_id = global_vpc.setup_vpc("vpc-12345", "us-east-1")
        self.assertIsNone(vpc)
        self.assertIsNone(gateway_id)

    @patch("global_vpc.boto3.client")
    def test_setup_security_groups_error_handling(self, mock_boto_client):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_vpc = MagicMock()
        mock_vpc.security_groups.all.return_value = [MagicMock(id="sg-12345")]
        mock_ec2.authorize_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "AuthorizeSecurityGroupIngress"
        )

        global_vpc.setup_security_groups(mock_ec2, mock_vpc)

    @patch("global_vpc.boto3.resource")
    def test_setup_route_tables_error_handling(self, mock_boto_resource):
        mock_ec2_resource = MagicMock()
        mock_boto_resource.return_value = mock_ec2_resource
        mock_vpc = MagicMock()
        mock_ec2_resource.Vpc.return_value = mock_vpc
        mock_vpc.route_tables.all.return_value = [MagicMock()]
        mock_vpc.route_tables.all.return_value[
            0
        ].create_route.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateRoute"
        )

        global_vpc.setup_route_tables(mock_vpc, "igw-12345")

    @patch("global_vpc.boto3.client")
    @patch("global_vpc.boto3.resource")
    def test_process_region_error_handling(self, mock_boto_resource, mock_boto_client):
        mock_ec2_client = MagicMock()
        mock_ec2_resource = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_boto_resource.return_value = mock_ec2_resource

        mock_ec2_client.describe_availability_zones.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "DescribeAvailabilityZones"
        )

        result = global_vpc.process_region("us-east-1", 11)
        self.assertIsNone(result)
        mock_ec2_client.describe_availability_zones.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "DescribeAvailabilityZones"
        )

        result = global_vpc.process_region("us-east-1", 11)
        self.assertIsNone(result)

    @patch("global_vpc.boto3.resource")
    def test_create_subnets_error_handling(self, mock_boto_resource):
        mock_ec2_resource = MagicMock()
        mock_boto_resource.return_value = mock_ec2_resource
        mock_vpc = MagicMock()
        mock_ec2_resource.Vpc.return_value = mock_vpc
        mock_vpc.create_subnet.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "CreateSubnet"
        )

        availability_zones = [{"ZoneName": "us-east-1a", "ZoneId": "use1-az1"}]
        subnets = global_vpc.create_subnets(mock_vpc, 11, availability_zones)
        self.assertIsNone(subnets)

    @patch("global_vpc.boto3.resource")
    def test_create_vpc_peering_error_handling(self, mock_boto_resource):
        mock_ec2_resource = MagicMock()
        mock_boto_resource.return_value = mock_ec2_resource
        mock_vpc = MagicMock()
        mock_ec2_resource.Vpc.return_value = mock_vpc
        mock_vpc.request_vpc_peering_connection.side_effect = ClientError(
            {"Error": {"Code": "Error"}}, "RequestVpcPeeringConnection"
        )

        vpcs = [
            {"Region": "us-east-1", "VpcId": "vpc-12345", "Cidr": "10.0.0.0/16"},
            {"Region": "us-west-1", "VpcId": "vpc-67890", "Cidr": "10.1.0.0/16"},
        ]

        global_vpc.create_peering(vpcs[0], vpcs[1])

    @patch(
        "global_vpc.get_all_regions",
        side_effect=ClientError({"Error": {"Code": "Error"}}, "DescribeRegions"),
    )
    @patch("builtins.input", return_value="yes")
    def test_main_get_all_regions_error(self, mock_input, mock_get_all_regions):
        with self.assertLogs(level="ERROR") as log:
            global_vpc.main()
            self.assertIn("Error in main execution", log.output[0])

    @patch("global_vpc.process_region", side_effect=Exception("Test Exception"))
    @patch(
        "global_vpc.get_all_regions",
        return_value=["us-east-1", "us-east-2", "us-west-1"],
    )
    @patch("builtins.input", return_value="yes")
    def test_main_process_region_error(
        self, mock_input, mock_get_all_regions, mock_process_region
    ):
        with self.assertLogs(level="ERROR") as log:
            global_vpc.main()
            self.assertIn("Error processing region", log.output[0])

    @patch("global_vpc.main")
    def test_main(self, mock_main):
        global_vpc.main()
        mock_main.assert_called_once()


if __name__ == "__main__":
    unittest.main()
