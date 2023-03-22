resource "yandex_compute_instance" "yc-node" {
  name                      = var.vm_name
  zone                      = "ru-central1-a"
  hostname                  = "${var.vm_name}.test.local"
  allow_stopping_for_update = true

  resources {
    cores         = var.vm_resources.cores
    memory        = var.vm_resources.memory
    core_fraction = var.vm_resources.core_fraction
  }

  scheduling_policy {
    preemptible = true
  }

  boot_disk {
    initialize_params {
      image_id    = "${var.centos-7-packer-image}"
      name        = "root-${var.vm_name}"
      type        = "network-hdd"
      size        = "20"
    }
  }

  network_interface {
    subnet_id = "${var.subnet_id}"
    nat       = true
  }

  metadata = {
    serial-port-enable = var.metadata.serial-port-enable
    ssh-keys           = var.ssh-keys
  }
}