variable "centos-7-packer-image" {
  default = "fd84do0f7buohu97oeb0"
}

variable "ubuntu-2204-lts" {
  default = "fd84do0f7buohu97oeb0"
}

variable "vm_name" {
  default = "pgsql-test"
}

variable "cloud_id" {
  type        = string
  description = "https://cloud.yandex.ru/docs/resource-manager/operations/cloud/get-id"
}

variable "folder_id" {
  type        = string
  description = "https://cloud.yandex.ru/docs/resource-manager/operations/folder/get-id"
}

variable "subnet_id" {
  type        = string
}

variable "vm_resources" {
    type = map(number)
    default = {
        cores = 4
        memory = 8
        core_fraction = 100
    }
}

variable "ssh-keys" {
  type        = string
}

variable "metadata" {
    type = map(string)
    default = {
        serial-port-enable = "1"
    }
}