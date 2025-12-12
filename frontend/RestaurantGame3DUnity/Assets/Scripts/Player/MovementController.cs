using System.Collections;

using System.Collections.Generic;

using UnityEngine;



public class MovementController : MonoBehaviour

{
    [SerializeField] private float speed;
    [SerializeField] private float sensitivity;
    private Rigidbody rb;
    private Animator anim;
    private Vector3 input;
    private float mouseInput;
    private Transform cam;
    private void Awake()
    {
        rb = GetComponent<Rigidbody>();
        anim = GetComponent<Animator>();
        // 獲取主攝影機的 Transform 引用
        if (Camera.main != null)
        {
            cam = Camera.main.transform;
        }
        else
        {
            Debug.LogError("Didn't find main camera");
        }
    }

    private void Update()
    {
        GetInput();
        UpdateAnimations();
        RotateChar();
    }

    private void RotateChar()

    {
        if (Input.GetMouseButton(1))
        {
            mouseInput = Input.GetAxis("Mouse X");
            transform.Rotate(Vector3.up * mouseInput * sensitivity);
            Cursor.lockState = CursorLockMode.Locked;
        }
        else if (Input.GetMouseButtonUp(1))
        {
            Cursor.lockState = CursorLockMode.None;
        }

    }

    private void UpdateAnimations()

    {

        if (input != Vector3.zero)
        {
            anim.SetBool("isMoving", true);
        }
        else
        {
            anim.SetBool("isMoving", false);
        }
    }

    private void GetInput()
    {
        input.z = Input.GetAxis("Vertical");
        input.x = Input.GetAxis("Horizontal");
    }

    private void FixedUpdate()
    {
        if (cam == null) return;

        Vector3 camForward = cam.forward;
        Vector3 camRight = cam.right;

        camForward.y = 0f; 
        camRight.y = 0f;

        camForward.Normalize();
        camRight.Normalize();

        Vector3 desiredMove = (camForward * input.z + camRight * input.x).normalized;

        if (desiredMove != Vector3.zero)
        {
            rb.MovePosition(transform.position + desiredMove * speed * Time.fixedDeltaTime);
            
            Quaternion newRotation = Quaternion.LookRotation(desiredMove);
            rb.MoveRotation(newRotation);
        }
        // rb.velocity += ((transform.forward * input.z) + (transform.right * input.x))*speed;
    }
}