plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "org.aegisneuro.watch"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.aegisneuro.aegisneuro"
        minSdk = 30
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    // Единый release keystore для phone + watch (пароли из env vars)
    signingConfigs {
        create("release") {
            storeFile = file(System.getenv("AEGIS_KEYSTORE") ?: "../keystore/aegisneuro-release.keystore")
            storePassword = System.getenv("AEGIS_KEYSTORE_PASS") ?: ""
            keyAlias = System.getenv("AEGIS_KEY_ALIAS") ?: "aegisneuro"
            keyPassword = System.getenv("AEGIS_KEY_PASS") ?: ""
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = false
        }
        debug {
            // debug тоже подписываем release-ключом, чтобы обновления работали
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.health:health-services-client:1.1.0-rc02")
    implementation("com.google.android.gms:play-services-wearable:19.0.0")
    implementation("com.google.guava:guava:33.3.1-android")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.9.0")
}