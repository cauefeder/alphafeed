package com.omnp.alphafeed

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.omnp.alphafeed.data.cache.*
import kotlinx.coroutines.test.runTest
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class BetDaoTest {
    private fun ent(id: String, ev: Int = 40) = BetEntity(id, id, ev, 50, 30, "STRONG", "MLB", null, 3.0)

    @Test fun replace_and_read() = runTest {
        val db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), AppDatabase::class.java).allowMainThreadQueries().build()
        db.betDao().replaceAll(listOf(ent("a", 47), ent("b", 40)))
        assertEquals(2, db.betDao().getAll().size)
        db.betDao().replaceAll(listOf(ent("c", 30)))
        assertEquals(listOf("c"), db.betDao().getAll().map { it.id })
        db.close()
    }
}
