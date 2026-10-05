output "vpc_id" {
  description = "VPC ID created by DeployHub networking module"
  value       = module.networking.vpc_id
}

output "security_group_id" {
  description = "Security Group ID created by DeployHub compute module"
  value       = module.compute.security_group_id
}
