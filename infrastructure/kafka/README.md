# Kafka local configuration

Kafka chạy combined broker/controller KRaft mode với replication factor `1`.
Đây là topology local development, không phải production high availability.

Configuration dùng environment-variable mapping của official Apache Kafka image:
<https://github.com/apache/kafka/blob/trunk/docker/examples/README.md#using-environment-variables>.
