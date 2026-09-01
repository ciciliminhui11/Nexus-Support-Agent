/**
 * 登录页：手机号/邮箱 + 密码。
 * 实时表单校验、错误内联、登录失败友好提示、redirect 回跳。
 */
import { useState } from "react";
import { Button, Card, Flex, Form, Input, Typography, App } from "antd";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { ApiError } from "@/api/http";
import {
  MIN_PASSWORD_LENGTH,
  detectIdentifierType,
  isValidPassword,
} from "@/utils/validation";

interface LoginFormValues {
  identifier: string;
  password: string;
}

export default function LoginPage() {
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const [submitting, setSubmitting] = useState(false);
  const { message } = App.useApp();

  const onFinish = async (values: LoginFormValues) => {
    const type = detectIdentifierType(values.identifier);
    if (!type) {
      message.error("请输入正确的手机号或邮箱");
      return;
    }
    setSubmitting(true);
    try {
      await login(values.identifier, type, values.password);
      const redirect = search.get("redirect");
      navigate(redirect || "/chat", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        // 统一失败提示，不暴露账号是否存在等敏感细节
        message.error(err.message || "登录失败，请检查账号或密码");
      } else {
        message.error("登录失败，请稍后重试");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Flex justify="center" align="center" style={{ minHeight: "100vh", background: "#f5f6fa" }}>
      <Card style={{ width: 400 }} styles={{ body: { padding: 32 } }}>
        <Flex vertical gap={4} style={{ marginBottom: 24 }}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            Nexus 智能客服
          </Typography.Title>
          <Typography.Text type="secondary">登录以继续</Typography.Text>
        </Flex>
        <Form<LoginFormValues> layout="vertical" onFinish={onFinish} requiredMark={false} autoComplete="off">
          <Form.Item
            name="identifier"
            label="手机号 / 邮箱"
            rules={[
              { required: true, message: "请输入手机号或邮箱" },
              {
                validator: (_rule, value: string) => {
                  if (!value || detectIdentifierType(value)) return Promise.resolve();
                  return Promise.reject(new Error("手机号或邮箱格式不正确"));
                },
              },
            ]}
          >
            <Input placeholder="请输入手机号或邮箱" size="large" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              {
                validator: (_rule, value: string) => {
                  if (!value) return Promise.resolve();
                  if (!isValidPassword(value)) {
                    return Promise.reject(new Error(`密码长度至少 ${MIN_PASSWORD_LENGTH} 位`));
                  }
                  return Promise.resolve();
                },
              },
            ]}
          >
            <Input.Password placeholder="请输入密码" size="large" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
              登录
            </Button>
          </Form.Item>
        </Form>
        <Flex justify="center">
          <Typography.Text type="secondary">
            还没有账号？<Link to="/register">去注册</Link>
          </Typography.Text>
        </Flex>
      </Card>
    </Flex>
  );
}
