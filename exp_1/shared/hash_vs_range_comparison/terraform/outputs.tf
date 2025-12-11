output "shard_0_endpoint" {
  description = "Shard 0 database endpoint"
  value       = aws_db_instance.shard_0.endpoint
}

output "shard_1_endpoint" {
  description = "Shard 1 database endpoint"
  value       = aws_db_instance.shard_1.endpoint
}

output "shard_2_endpoint" {
  description = "Shard 2 database endpoint"
  value       = aws_db_instance.shard_2.endpoint
}

output "shard_3_endpoint" {
  description = "Shard 3 database endpoint"
  value       = aws_db_instance.shard_3.endpoint
}

output "connection_info" {
  description = "Connection information for all shards"
  value = {
    shard_0 = {
      host     = split(":", aws_db_instance.shard_0.endpoint)[0]
      port     = 3306
      database = "coupon_db_0"
      username = var.db_username
    }
    shard_1 = {
      host     = split(":", aws_db_instance.shard_1.endpoint)[0]
      port     = 3306
      database = "coupon_db_1"
      username = var.db_username
    }
    shard_2 = {
      host     = split(":", aws_db_instance.shard_2.endpoint)[0]
      port     = 3306
      database = "coupon_db_2"
      username = var.db_username
    }
    shard_3 = {
      host     = split(":", aws_db_instance.shard_3.endpoint)[0]
      port     = 3306
      database = "coupon_db_3"
      username = var.db_username
    }
  }
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost (USD)"
  value       = "Approximately $60-80/month (4 x db.t3.micro RDS instances)"
}

