FROM php:8.2-apache

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/*

RUN a2enmod rewrite

COPY php.ini /usr/local/etc/php/conf.d/99-sandbox.ini
COPY fake-sendmail.sh /usr/local/bin/fake-sendmail
COPY apache-sandbox.conf /etc/apache2/conf-available/sandbox.conf

RUN chmod +x /usr/local/bin/fake-sendmail \
    && mkdir -p /var/log/php-mail /var/www/html \
    && chown -R www-data:www-data /var/log/php-mail /var/www/html \
    && a2enconf sandbox

EXPOSE 80
