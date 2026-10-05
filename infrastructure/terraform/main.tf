module "networking" {
  source      = "./modules/networking"
  vpc_cidr    = var.vpc_cidr
  environment = var.environment
}

module "compute" {
  source      = "./modules/compute"
  vpc_id      = module.networking.vpc_id
  subnet_id   = module.networking.public_subnet_id
  environment = var.environment
}
