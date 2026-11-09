terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  host = "unix://${pathexpand("~/.docker/run/docker.sock")}"
}

resource "docker_network" "fleetflow" {
  name = "fleetflow-net"
}

resource "docker_image" "postgres" {
  name         = "postgres:16"
  keep_locally = true
}

resource "docker_container" "db" {
  name  = "fleetflow-tf-db"
  image = docker_image.postgres.image_id
  env = [
    "POSTGRES_PASSWORD=${var.db_password}",
    "POSTGRES_DB=fleetflow",
  ]
  ports {
    internal = 5432
    external = var.db_port
  }
  networks_advanced {
    name = docker_network.fleetflow.name
  }
}