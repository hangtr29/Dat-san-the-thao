import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='Tên gói dịch vụ')),
                ('duration_days', models.IntegerField(default=30, verbose_name='Thời lượng (ngày)')),
                ('price', models.DecimalField(decimal_places=0, max_digits=12, verbose_name='Giá gói (VNĐ)')),
                ('description', models.TextField(blank=True, verbose_name='Mô tả quyền lợi')),
                ('is_active', models.BooleanField(default=True, verbose_name='Đang mở bán')),
            ],
            options={
                'verbose_name': 'Gói phí duy trì',
                'verbose_name_plural': 'Danh mục gói phí duy trì',
                'ordering': ['price'],
            },
        ),
        migrations.CreateModel(
            name='OwnerProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('id_card_number', models.CharField(blank=True, default='', max_length=25, verbose_name='Số CCCD / Hộ chiếu')),
                ('id_card_front', models.ImageField(blank=True, null=True, upload_to='kyc/id_cards/', verbose_name='Ảnh CCCD mặt trước')),
                ('id_card_back', models.ImageField(blank=True, null=True, upload_to='kyc/id_cards/', verbose_name='Ảnh CCCD mặt sau')),
                ('business_license', models.ImageField(blank=True, null=True, upload_to='kyc/licenses/', verbose_name='Giấy phép KD / Hợp đồng thuê đất')),
                ('bank_name', models.CharField(blank=True, default='', max_length=50, verbose_name='Tên ngân hàng (VD: MBBank, VCB)')),
                ('bank_account_number', models.CharField(blank=True, default='', max_length=50, verbose_name='Số tài khoản ngân hàng')),
                ('bank_account_holder', models.CharField(blank=True, default='', max_length=150, verbose_name='Tên chủ tài khoản')),
                ('bank_qr_image', models.ImageField(blank=True, null=True, upload_to='kyc/qrcodes/', verbose_name='Ảnh mã VietQR')),
                ('kyc_status', models.CharField(choices=[('KYC_PENDING', 'Chờ xác minh'), ('KYC_VERIFIED', 'Đã xác minh (Tích xanh)'), ('KYC_REJECTED', 'Bị từ chối')], default='KYC_PENDING', max_length=20, verbose_name='Trạng thái xác minh KYC')),
                ('kyc_rejection_reason', models.TextField(blank=True, null=True, verbose_name='Lý do từ chối KYC')),
                ('subscription_expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Thời hạn gói dịch vụ duy trì')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Ngày đăng ký')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Cập nhật lần cuối')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='owner_profile', to=settings.AUTH_USER_MODEL, verbose_name='Tài khoản chủ sân')),
            ],
            options={
                'verbose_name': 'Hồ sơ xác minh chủ sân (KYC)',
                'verbose_name_plural': 'Danh sách hồ sơ chủ sân (KYC)',
            },
        ),
        migrations.CreateModel(
            name='SubscriptionOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('order_code', models.CharField(max_length=30, unique=True, verbose_name='Mã đơn đăng ký')),
                ('amount', models.DecimalField(decimal_places=0, max_digits=12, verbose_name='Số tiền thanh toán (VNĐ)')),
                ('payment_proof', models.ImageField(blank=True, null=True, upload_to='subscription_proofs/', verbose_name='Ảnh biên lai chuyển khoản')),
                ('status', models.CharField(choices=[('PENDING', 'Chờ Ban quản trị duyệt'), ('APPROVED', 'Đã duyệt kích hoạt'), ('REJECTED', 'Bị từ chối')], default='PENDING', max_length=20, verbose_name='Trạng thái đơn')),
                ('rejection_reason', models.TextField(blank=True, null=True, verbose_name='Lý do từ chối')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo đơn')),
                ('approved_at', models.DateTimeField(blank=True, null=True, verbose_name='Thời điểm duyệt')),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_subscriptions', to=settings.AUTH_USER_MODEL, verbose_name='Người duyệt')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscription_orders', to=settings.AUTH_USER_MODEL, verbose_name='Chủ sân')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='users.subscriptionplan', verbose_name='Gói dịch vụ')),
            ],
            options={
                'verbose_name': 'Đơn đăng ký gói phí duy trì',
                'verbose_name_plural': 'Danh sách đơn đăng ký gói phí',
                'ordering': ['-created_at'],
            },
        ),
    ]

