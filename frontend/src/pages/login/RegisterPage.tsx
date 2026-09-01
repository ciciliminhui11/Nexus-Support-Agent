/**
 * 注册页：手机号/邮箱 + 密码 + 确认密码。
 * 实时校验（格式/长度/两次一致）、注册成功自动登录进入主界面。
 */
import { useState } from "react";
import { Button, Card, Flex, Form, Input, Typography, App } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { ApiError } from "@/api/http";
import {
  MIN_PASSWORD_LENGTH,
  detectIdentifierType,
  isValidPassword,
  passwordsMatch,
} from "@/utils/validation";

interface RegisterFormValues {
  identifier: string;
  password: string;
  confirm: string;
}

export default function RegisterPage() {
  const register = useAuthStore((s) => s.register);
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const { message } = App.useApp();

  const onFinish = async (values: RegisterFormValues) => {
    const type = detectIdentifierType(values.identifier);
    if (!type) {
      message.error("请输入正确的手机号或邮箱");
      return;
    }
    setSubmitting(true);
    try {
      await register(values.identifier, type, values.password);
      message.success("注册成功，已自动登录");
      navigate("/chat", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        message.error(err.message || "注册失败");
      } else {
        message.error("注册失败，请稍后重试");
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
          <Typography.Text type="secondary">创建新账号</Typography.Text>
        </Flex>
        <Form<RegisterFormValues> layout="vertical" onFinish={onFinish} requiredMark={false} autoComplete="off">
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
            <Input.Password placeholder="至少 8 位密码" size="large" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请再次输入密码" },
              ({ getFieldValue }) => ({
                validator: (_rule, value: string) => {
                  if (!value) return Promise.resolve();
                  if (!passwordsMatch(getFieldValue("password") ?? "", value)) {
                    return Promise.reject(new Error("两次输入的密码不一致"));
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入密码" size="large" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
              注册
            </Button>
          </Form.Item>
        </Form>
        <Flex justify="center">
          <Typography.Text type="secondary">
            已有账号？<Link to="/login">去登录</Link>
          </Typography.Text>
        </Flex>
      </Card>
    </Flex>
  );
}
