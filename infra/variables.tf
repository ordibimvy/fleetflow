variable "db_password" {
  type      = string
  default   = "postgres"
  sensitive = true
}

variable "db_port" {
  type    = number
  default = 5433
}