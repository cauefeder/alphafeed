package com.omnp.alphafeed.data.cache

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Transaction

@Dao
interface BetDao {
    @Query("SELECT * FROM bets")
    suspend fun getAll(): List<BetEntity>

    @Transaction
    suspend fun replaceAll(items: List<BetEntity>) {
        clear()
        insert(items)
    }

    @Query("DELETE FROM bets")
    suspend fun clear()

    @Insert
    suspend fun insert(items: List<BetEntity>)
}
