from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('facilities', '0003_facilityreview'),
    ]

    operations = [
        migrations.AddField(
            model_name='facility',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='facilities/', verbose_name='Ảnh bìa cụm sân'),
        ),
        migrations.AddField(
            model_name='facility',
            name='custom_qr_image',
            field=models.ImageField(blank=True, null=True, upload_to='qrcodes/', verbose_name='Ảnh mã QR thanh toán (Tùy chọn)'),
        ),
        migrations.AddField(
            model_name='facilityreview',
            name='owner_reply',
            field=models.TextField(blank=True, null=True, verbose_name='Phản hồi của Chủ sân'),
        ),
        migrations.AddField(
            model_name='facilityreview',
            name='owner_reply_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Thời gian chủ sân phản hồi'),
        ),
    ]

