variable "aws_region" {
  description = "AWS region for resources"
  type        = "string"
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = "string"
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for DeployHub VPC"
  type        = "string"
  default     = "10.0.0.0/16"
}

variable "cluster_name" {
  description = "Name of the Kubernetes cluster"
  type        = "string"
  default     = "deployhub-cluster"
}
