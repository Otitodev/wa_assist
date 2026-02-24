import { betterAuth } from "better-auth";
import { Pool } from "pg";
import { Resend } from "resend";

const resend = new Resend(process.env.RESEND_API_KEY);

export const auth = betterAuth({
  database: new Pool({ connectionString: process.env.DATABASE_URL }),
  secret: process.env.BETTER_AUTH_SECRET,
  emailAndPassword: {
    enabled: true,
    sendResetPassword: async ({ user, url }) => {
      await resend.emails.send({
        from: "Whaply <otito@addpost.site>",
        to: user.email,
        subject: "Reset your Whaply password",
        html: `
          <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px;">
            <h2 style="color:#16a34a;">Reset your password</h2>
            <p>Hi ${user.name || user.email},</p>
            <p>Click the button below to reset your Whaply password. This link expires in 1 hour.</p>
            <a href="${url}" style="display:inline-block;padding:12px 28px;background:#16a34a;color:white;text-decoration:none;border-radius:8px;font-weight:500;margin:16px 0;">
              Reset Password
            </a>
            <p style="color:#6b7280;font-size:0.875rem;margin-top:24px;">
              If you didn't request this, you can safely ignore this email.
            </p>
          </div>
        `,
      });
    },
  },
  user: {
    additionalFields: {
      display_name: { type: "string", required: false, defaultValue: "" },
    },
  },
});
