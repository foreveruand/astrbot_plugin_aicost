# AI Cost Monitor - AstrBot Plugin

AI 服务费用查询插件，支持多种 AI 服务的费用查询和报告生成。

## 支持的服务

- **Azure OpenAI** - 通过 Cost Management API 查询本月费用
- **OpenRouter** - 查询账户余额和使用情况
- **Google Gemini** - 通过 BigQuery 查询 Gemini API 费用
- **xAI Grok** - 查询账户余额和使用情况

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
playwright install chromium
```

2. 在 AstrBot 插件目录中放置此插件

## 配置

在 AstrBot 管理面板中配置以下参数：

### 通用配置
| 参数 | 说明 |
|------|------|
| `enable_daily_report` | 启用每日定时报告 |
| `report_time` | 每日报告时间 (HH:MM) |

### Azure OpenAI
| 参数 | 说明 |
|------|------|
| `azure_tenant_id` | Azure 租户 ID |
| `azure_client_id` | Azure 客户端 ID |
| `azure_client_secret` | Azure 客户端密钥 |
| `azure_subscription_id` | Azure 订阅 ID |

### OpenRouter
| 参数 | 说明 |
|------|------|
| `openrouter_api_key` | OpenRouter API Key |

### Google Cloud
| 参数 | 说明 |
|------|------|
| `google_project_id` | Google Cloud 项目 ID |
| `google_bq_table` | BigQuery 账单表地址 |
| `google_service_account_json` | 服务账号 JSON 文件路径 |

### xAI
| 参数 | 说明 |
|------|------|
| `xai_api_key` | xAI API Key |
| `xai_team_id` | xAI Team ID |

## 使用

发送命令：
```
/aicost
```

插件将查询所有已配置的服务并生成一份图片报告。

## 注意事项

1. **Google BigQuery** 需要：
   - 在 Google Cloud Console 中启用 BigQuery API
   - 导出账单数据到 BigQuery
   - 配置服务账号权限

2. **Playwright** 用于生成图片报告，首次使用需要安装浏览器：
   ```bash
   playwright install chromium
   ```