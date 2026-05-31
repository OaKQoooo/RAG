package com.example.damrag.repository;

import com.example.damrag.model.AdminActivity;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AdminActivityRepository extends JpaRepository<AdminActivity, Long> {
    List<AdminActivity> findTop20ByOrderByCreatedAtDesc();
}
