# Database Connection Troubleshooting

## Symptoms
- "Connection refused" errors
- "Too many connections" errors
- Timeouts on database queries

## Common Causes
1. Security group misconfiguration
2. Connection pool exhaustion
3. Database instance down or rebooting
4. Network connectivity issues

## Resolution Steps

### 1. Check Security Group
```bash
# Verify security group allows port 5432 (PostgreSQL) or 3306 (MySQL)
aws ec2 describe-security-groups --group-ids sg-YOUR_GROUP_ID
```

### 2. Check Connection Pool
```bash
# Review application logs for pool stats
kubectl logs deployment/api-service | grep "HikariPool"

# Restart to reset pool
kubectl rollout restart deployment/api-service
```

### 3. Check RDS Status
```bash
aws rds describe-db-instances \
  --db-instance-identifier your-db \
  --query 'DBInstances[0].[DBInstanceStatus,Endpoint]'
```

### 4. Verify Credentials
- Check AWS Secrets Manager for correct credentials
- Verify IAM database authentication if using it

## Prevention
- Set up CloudWatch alarms for connection count
- Configure connection pool properly (min: 5, max: 20)
- Enable enhanced monitoring on RDS

## Related Incidents
- INC-2024-031 (Jan 15, 2024) - Security group issue
- INC-2024-045 (Feb 3, 2024) - Connection pool exhaustion
