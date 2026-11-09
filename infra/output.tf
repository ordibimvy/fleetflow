output "database_url" {
  value     = "postgresql://postgres:${var.db_password}@localhost:${var.db_port}/fleetflow"
  sensitive = true
}
