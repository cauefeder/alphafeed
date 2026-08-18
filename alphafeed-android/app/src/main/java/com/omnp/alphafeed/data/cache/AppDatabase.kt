package com.omnp.alphafeed.data.cache

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [BetEntity::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun betDao(): BetDao
}
