# SkipCash Payment Gateway for Odoo

This module integrates SkipCash, a popular payment gateway in Qatar, with Odoo's eCommerce and invoicing platform. It allows you to accept online payments from your customers securely.

## Prerequisites

Before installing the module, you must install the official `skipcash` Python library in your Odoo environment.

Connect to your Odoo server via SSH and run the following command:

```bash
pip install skipcash
```

## Configuration

To get started, you need to configure both your Odoo instance and your SkipCash merchant portal.

### 1. Configuration in Odoo

Follow these steps to set up the SkipCash payment provider in Odoo:

1.  Navigate to **Accounting** or **Website** ‣ Configuration ‣ Payment Providers.
2.  Search for **SkipCash** and open it.
3.  Fill in the credentials obtained from your SkipCash merchant account:
    *   **Skipcash Key ID**
    *   **Skipcash Webhook Key**
    *   **Skipcash Client ID**
    *   **Skipcash Secret**
4.  Set the **State** of the provider:
    *   **Test Mode**: Use this for testing transactions with sandbox credentials.
    *   **Enabled (Production)**: Use this for processing live payments with production credentials.
5.  Configure the **Payment Journal** and other settings as needed.
6.  Click **Save**.

### 2. Configuration in SkipCash Merchant Portal

You must provide your Odoo instance's callback URLs to your SkipCash merchant portal to ensure that payment statuses are communicated correctly.

1.  Log in to your SkipCash merchant portal.
2.  Navigate to the API settings or Webhooks section.
3.  You will be asked to provide the following URLs. Replace `{{ODOO_URL}}` with your actual Odoo domain (e.g., `https://yourcompany.com`).

    *   **Webhook URL:**
        ```
        {{ODOO_URL}}/payment/skipcash/webhook
        ```
        This URL is used for server-to-server communication to confirm payment status asynchronously.

    *   **Return URL:**
        ```
        {{ODOO_URL}}/payment/skipcash/return
        ```
        This is the URL where customers are redirected after completing a payment on the SkipCash page.

4.  Save the changes in your SkipCash portal.

Your integration is now complete and ready to accept payments.
