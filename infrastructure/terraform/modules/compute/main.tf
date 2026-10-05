resource "aws_security_group" "k8s_sg" {
  name        = "deployhub-k8s-sg-${var.environment}"
  description = "Security group for DeployHub cluster nodes"
  vpc_id      = var.vpc_id

  # Allow HTTP / HTTPS inbound
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "deployhub-k8s-sg-${var.environment}"
  }
}
