import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('facilities', '0002_initial'),
        ('bookings', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FacilityReview',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reviewer_name', models.CharField(max_length=150, verbose_name='Tên người đánh giá')),
                ('rating', models.IntegerField(choices=[(1, '1 Sao - Rất tệ'), (2, '2 Sao - Tệ'), (3, '3 Sao - Bình thường'), (4, '4 Sao - Tốt'), (5, '5 Sao - Xuất sắc')], default=5, verbose_name='Số sao đánh giá (1-5)')),
                ('comment', models.TextField(verbose_name='Nhận xét chất lượng sân')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Thời gian đánh giá')),
                ('booking', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='review', to='bookings.booking', verbose_name='Đơn đặt sân đã xác thực')),
                ('facility', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='facilities.facility', verbose_name='Cụm sân')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='facility_reviews', to=settings.AUTH_USER_MODEL, verbose_name='Khách hàng')),
            ],
            options={
                'verbose_name': 'Đánh giá cụm sân',
                'verbose_name_plural': 'Danh sách đánh giá cụm sân',
                'ordering': ['-created_at'],
            },
        ),
    ]

