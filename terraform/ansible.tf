resource "null_resource" "cluster" {
  provisioner "local-exec" {
    command = "ANSIBLE_FORCE_COLOR=1 ansible-playbook -i ansible/inventory ansible/provision.yml"
  }

  depends_on = [yandex_compute_instance.yc-node, local_file.inventory]
}
