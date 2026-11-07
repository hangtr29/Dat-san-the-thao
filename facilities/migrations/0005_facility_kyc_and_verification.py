from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facilities', '0004_facility_image_custom_qr_and_review_reply'),
        ('facilities', '0004_facility_latitude_facility_longitude'),
    ]

    operations = [
        migrations.AddField(
            model_name='facility',
            name='hotline',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Hotline chính thức'),
        ),
        migrations.AddField(
            model_name='facility',
            name='is_verified',
            field=models.BooleanField(db_index=True, default=True, verbose_name='Đã xác thực (Tích xanh)'),
        ),
        migrations.AddField(
            model_name='facility',
            name='reputation_score',
            field=models.FloatField(default=5.0, verbose_name='Điểm uy tín (1-5)'),
        ),
        migrations.AddField(
            model_name='facility',
            name='status',
            field=models.CharField(choices=[('PENDING_REVIEW', 'Chờ duyệt hồ sơ'), ('ACTIVE', 'Đang hoạt động'), ('SUSPENDED', 'Tạm ngưng hoạt động')], db_index=True, default='ACTIVE', max_length=20, verbose_name='Trạng thái hoạt động'),
        ),
    ]

