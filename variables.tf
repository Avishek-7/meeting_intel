# variables.tf
variable "db_user" {
  default = "meeting_intel"
}

variable "db_password" {
  sensitive = true
}

variable "db_name" {
  default = "meeting_intel_db"
}
