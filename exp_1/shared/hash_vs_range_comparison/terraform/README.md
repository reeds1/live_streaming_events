# AWS Deployment with Terraform

This Terraform configuration deploys the Hash vs Range sharding comparison experiment on AWS.

## Architecture

- **4 RDS MySQL instances** (one per shard)
- **VPC** with public subnets in 2 availability zones
- **Security groups** for database access
- Instance type: `db.t3.micro` (free tier eligible)

## Prerequisites

1. **AWS CLI configured**:
   ```bash
   aws configure
   # Or export credentials:
   export AWS_ACCESS_KEY_ID="your-key"
   export AWS_SECRET_ACCESS_KEY="your-secret"
   export AWS_DEFAULT_REGION="us-east-1"
   ```

2. **Terraform installed** (v1.0+)

## Cost Estimate

- **4 x db.t3.micro RDS instances**: ~$60-80/month
- **Data transfer**: Minimal for testing
- **Total**: ~$60-80/month

⚠️ **Remember to destroy resources after testing to avoid charges!**

## Deployment Steps

### 1. Configure AWS Credentials

```bash
# Check if credentials are valid
aws sts get-caller-identity

# If expired, reconfigure:
aws configure
```

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Review the Plan

```bash
terraform plan
```

This will show you what resources will be created.

### 4. Deploy

```bash
terraform apply

# Type 'yes' when prompted
```

**Deployment time**: ~10-15 minutes (RDS instances take time to provision)

### 5. Get Connection Info

```bash
terraform output
```

This will show you the endpoints for all 4 shards.

### 6. Update Database Configuration

The output will give you endpoints like:
```
shard_0_endpoint = "hash-range-shard-0.xxxxx.us-east-1.rds.amazonaws.com:3306"
```

Update `strategies/database.py` with these endpoints.

### 7. Run Tests

```bash
cd ../strategies
python3 init_hash_shards.py
python3 init_range_shards.py

cd ../tests
python3 comparison_experiment.py
```

### 8. Destroy Resources (IMPORTANT!)

```bash
cd terraform
terraform destroy

# Type 'yes' when prompted
```

## Security Notes

⚠️ **For testing only!**

- RDS instances are publicly accessible
- Security group allows all IPs (0.0.0.0/0)
- **In production**: Restrict to specific IPs

## Customization

Edit `variables.tf` to change:
- AWS region
- Instance type (for better performance: `db.t3.small` or `db.t3.medium`)
- Database password

## Troubleshooting

### AWS Token Expired

```bash
aws configure
# Re-enter your credentials
```

### RDS Creation Failed

- Check AWS quota limits for RDS instances
- Ensure you have permissions to create RDS instances
- Try a different region if capacity issues

### Connection Timeout

- Wait 5 minutes after `terraform apply` for RDS to be fully ready
- Check security group rules
- Verify RDS instances are in "Available" state:
  ```bash
  aws rds describe-db-instances --query "DBInstances[*].[DBInstanceIdentifier,DBInstanceStatus]"
  ```

## Files Created

- `main.tf` - Main infrastructure configuration
- `variables.tf` - Input variables
- `outputs.tf` - Output values (endpoints)
- `terraform.tfstate` - State file (DO NOT DELETE)

## Clean Up Checklist

- [ ] Run `terraform destroy`
- [ ] Verify in AWS Console that all RDS instances are deleted
- [ ] Check for any leftover resources (VPC, subnets, security groups)

